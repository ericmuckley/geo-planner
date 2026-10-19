#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <utility>
#include <vector>

using Clock = std::chrono::steady_clock;
using Cost = std::uint64_t;
constexpr Cost infinity = std::numeric_limits<Cost>::max();

double milliseconds(Clock::time_point start) {
  return std::chrono::duration<double, std::milli>(Clock::now() - start).count();
}

std::uint32_t little32(const std::vector<unsigned char>& bytes, std::size_t offset) {
  return std::uint32_t(bytes.at(offset)) | (std::uint32_t(bytes.at(offset + 1)) << 8) |
         (std::uint32_t(bytes.at(offset + 2)) << 16) | (std::uint32_t(bytes.at(offset + 3)) << 24);
}

Cost number(const std::string& value) {
  Cost result = 0;
  const auto parsed = std::from_chars(value.data(), value.data() + value.size(), result);
  if (value.empty() || parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size())
    throw std::runtime_error("Expected an unsigned integer");
  return result;
}

std::vector<unsigned char> hex_identity(const std::string& value) {
  if (value.size() != 64) throw std::runtime_error("Expected 64-character graph identity");
  std::vector<unsigned char> result;
  for (std::size_t i = 0; i < value.size(); i += 2) {
    unsigned byte = 0;
    const auto parsed = std::from_chars(value.data() + i, value.data() + i + 2, byte, 16);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + i + 2)
      throw std::runtime_error("Invalid graph identity");
    result.push_back(static_cast<unsigned char>(byte));
  }
  return result;
}

struct Graph {
  std::vector<std::uint32_t> offsets, targets, weights;
  std::uint64_t bytes = 0;
  std::uint32_t states = 0;
};

Graph load_graph(const std::string& path, const std::string& identity) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input) throw std::runtime_error("Cannot open packed graph");
  const auto length = input.tellg();
  if (length < 48) throw std::runtime_error("Truncated graph header");
  std::vector<unsigned char> data(static_cast<std::size_t>(length));
  input.seekg(0);
  if (!input.read(reinterpret_cast<char*>(data.data()), length))
    throw std::runtime_error("Incomplete graph read");
  const std::string magic(data.begin(), data.begin() + 8);
  if (magic != "GPCSR001") throw std::runtime_error("Unsupported graph format");
  const auto expected_identity = hex_identity(identity);
  if (!std::equal(expected_identity.begin(), expected_identity.end(), data.begin() + 16))
    throw std::runtime_error("Graph identity mismatch");
  Graph graph;
  graph.states = little32(data, 8);
  const auto arcs = little32(data, 12);
  const std::uint64_t expected = 48 + 4 * (std::uint64_t(graph.states) + 1) + 8 * std::uint64_t(arcs);
  if (!graph.states || expected != data.size()) throw std::runtime_error("Packed graph size mismatch");
  graph.bytes = data.size();
  std::size_t offset = 48;
  graph.offsets.reserve(std::size_t(graph.states) + 1);
  for (std::uint64_t i = 0; i <= graph.states; ++i, offset += 4)
    graph.offsets.push_back(little32(data, offset));
  if (graph.offsets.front() != 0 || graph.offsets.back() != arcs ||
      !std::is_sorted(graph.offsets.begin(), graph.offsets.end()))
    throw std::runtime_error("Invalid adjacency offsets");
  graph.targets.reserve(arcs);
  graph.weights.reserve(arcs);
  for (std::uint64_t i = 0; i < arcs; ++i, offset += 4) {
    const auto target = little32(data, offset);
    if (target >= graph.states) throw std::runtime_error("Invalid arc target");
    graph.targets.push_back(target);
  }
  for (std::uint64_t i = 0; i < arcs; ++i, offset += 4)
    graph.weights.push_back(little32(data, offset));
  return graph;
}

std::uint64_t rss_kib() {
  rusage usage{};
  if (getrusage(RUSAGE_SELF, &usage) != 0) return 0;
#ifdef __APPLE__
  return static_cast<std::uint64_t>(usage.ru_maxrss) / 1024;
#else
  return static_cast<std::uint64_t>(usage.ru_maxrss);
#endif
}

void query(const Graph& graph, const std::string& line) {
  std::istringstream input(line);
  std::string id_text, budget_text, mode, count_text;
  if (!(input >> id_text >> budget_text >> mode >> count_text))
    throw std::runtime_error("Incomplete query header");
  const Cost id = number(id_text);
  const bool complete = budget_text == "full";
  const Cost budget = complete ? infinity - 1 : number(budget_text);
  if (budget == infinity || (mode != "labels" && mode != "membership"))
    throw std::runtime_error("Invalid budget or output mode");
  const Cost seed_count = number(count_text);
  if (!seed_count || seed_count > graph.states) throw std::runtime_error("Invalid seed count");
  const auto setup_start = Clock::now();
  std::vector<Cost> labels(graph.states, infinity);
  using Entry = std::pair<Cost, std::uint32_t>;
  std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
  std::uint64_t pushes = 0;
  for (Cost i = 0; i < seed_count; ++i) {
    std::string state_text, cost_text;
    if (!(input >> state_text >> cost_text)) throw std::runtime_error("Incomplete query seeds");
    const Cost state = number(state_text), cost = number(cost_text);
    if (state >= graph.states || cost > std::numeric_limits<std::uint32_t>::max())
      throw std::runtime_error("Invalid source state/attachment");
    if (cost <= budget && cost < labels[state]) {
      labels[state] = cost;
      queue.emplace(cost, static_cast<std::uint32_t>(state));
      ++pushes;
    }
  }
  std::string extra;
  if (input >> extra) throw std::runtime_error("Unexpected query fields");
  const double setup_ms = milliseconds(setup_start);
  std::uint64_t settled = 0, scanned = 0, queue_peak = queue.size();
  const auto search_start = Clock::now();
  while (!queue.empty()) {
    const auto [cost, state] = queue.top();
    queue.pop();
    if (labels[state] != cost) continue;
    ++settled;
    for (std::uint64_t arc = graph.offsets[state]; arc < graph.offsets[state + 1]; ++arc) {
      ++scanned;
      const Cost weight = graph.weights[arc];
      // This also prevents overflow for arbitrary bounded requests.
      if (weight > budget - cost) continue;
      const Cost candidate = cost + weight;
      const auto target = graph.targets[arc];
      if (candidate < labels[target]) {
        labels[target] = candidate;
        queue.emplace(candidate, target);
        ++pushes;
        queue_peak = std::max(queue_peak, std::uint64_t(queue.size()));
      }
    }
  }
  const double search_ms = milliseconds(search_start);
  const auto encode_start = Clock::now();
  std::vector<unsigned char> payload(mode == "labels" ? std::size_t(graph.states) * 8 : (std::size_t(graph.states) + 7) / 8, 0);
  if (mode == "labels") {
    for (std::size_t state = 0; state < graph.states; ++state)
      for (unsigned byte = 0; byte < 8; ++byte)
        payload[state * 8 + byte] = static_cast<unsigned char>(labels[state] >> (8 * byte));
  } else {
    for (std::size_t state = 0; state < graph.states; ++state)
      if (labels[state] != infinity) payload[state / 8] |= static_cast<unsigned char>(1u << (state % 8));
  }
  const double encode_ms = milliseconds(encode_start);
  std::cout << "{\"requestId\":" << id << ",\"complete\":" << (complete ? "true" : "false")
            << ",\"budgetMs\":" << (complete ? "null" : std::to_string(budget))
            << ",\"mode\":\"" << mode << "\",\"sourceSetupMs\":" << setup_ms
            << ",\"searchMs\":" << search_ms << ",\"encodeMs\":" << encode_ms
            << ",\"settledStates\":" << settled << ",\"scannedArcs\":" << scanned
            << ",\"heapPushes\":" << pushes << ",\"queuePeak\":" << queue_peak
            << ",\"payloadBytes\":" << payload.size() << ",\"maxRssKiB\":" << rss_kib() << "}\n";
  std::cout.write(reinterpret_cast<const char*>(payload.data()), static_cast<std::streamsize>(payload.size()));
  std::cout.flush();
  if (!std::cout) throw std::runtime_error("Result transfer failed");
}

int main(int argc, char** argv) {
  try {
    if (argc != 3) throw std::runtime_error("Usage: native_search GRAPH GRAPH_ID");
    std::cout.precision(9);
    const auto start = Clock::now();
    const Graph graph = load_graph(argv[1], argv[2]);
    std::cout << "{\"program\":\"csr-dijkstra-v1\",\"states\":" << graph.states
              << ",\"arcs\":" << graph.targets.size() << ",\"graphBytes\":" << graph.bytes
              << ",\"loadValidateMs\":" << milliseconds(start) << "}\n" << std::flush;
    std::string line;
    while (std::getline(std::cin, line)) {
      if (line.size() > 1024 * 1024) throw std::runtime_error("Query line too large");
      query(graph, line);
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
