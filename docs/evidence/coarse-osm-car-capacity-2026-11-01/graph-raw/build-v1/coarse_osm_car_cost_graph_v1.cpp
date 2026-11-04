// Draft offline cost facts. The original native source validator stays sealed.
#include "coarse_osm_topology_source_v1.cpp"
#include "coarse_osm_car_native_policy_v1.hpp"
#include "coarse_osm_car_cost_math_v1.hpp"
#include "coarse_osm_car_node_prepare_v1.hpp"
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>

namespace car_cost_graph {
constexpr std::uint64_t mib = 1048576, output_limit = 1792*mib;
struct Output {
    std::string root;
    std::uint64_t bytes = 0;
};
class Chunks {
    Output& output_;
    std::string prefix_;
    int fd_ = -1;
    std::FILE* stream_ = nullptr;
    std::array<char, 65536> buffer_{};
    std::uint32_t part_ = 0, size_ = 0;
    void close() {
        if (fd_ < 0) return;
        struct stat state{};
        const bool flushed = std::fflush(stream_) == 0;
        const bool ok = ::fstat(fd_, &state) == 0 && S_ISREG(state.st_mode) && state.st_nlink == 1 && state.st_size == size_;
        const int result = std::fclose(stream_); stream_ = nullptr; fd_ = -1;
        need(flushed && ok && result == 0, "cost_chunk_close");
    }
public:
    Chunks(Output& output, std::string prefix): output_(output), prefix_(std::move(prefix)) {}
    ~Chunks() { if (stream_) std::fclose(stream_); else if (fd_ >= 0) ::close(fd_); }
    void append(const void* data, std::size_t bytes) {
        need(bytes <= output_limit-output_.bytes && (!bytes || data), "cost_owned_output_cap");
        const auto* cursor = static_cast<const unsigned char*>(data);
        while (bytes) {
            if (fd_ < 0) {
                char name[64]; std::snprintf(name, sizeof(name), "/%s-%04u.bin", prefix_.c_str(), part_++);
                fd_ = ::open((output_.root+name).c_str(), O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW, 0600);
                need(fd_ >= 0, "cost_fresh_chunk"); size_ = 0;
                stream_ = ::fdopen(fd_, "wb");
                if (!stream_) { ::close(fd_); fd_ = -1; throw Failure{"cost_chunk_stream"}; }
                need(std::setvbuf(stream_, buffer_.data(), _IOFBF, buffer_.size()) == 0, "cost_chunk_buffer");
            }
            const auto count = std::min<std::size_t>(bytes, 16*mib-size_);
            const auto done = std::fwrite(cursor, 1, count, stream_);
            need(done > 0, "cost_chunk_write");
            size_ += done; output_.bytes += done; cursor += done; bytes -= done;
            if (size_ == 16*mib) close();
        }
    }
    template<class T> void row(const T& value) { append(&value, sizeof(value)); }
    void finish() { close(); }
};
struct Way {
    std::uint64_t id;
    double forward, backward;
    std::uint32_t flags, geometry_end;
};
struct Arc {
    std::uint32_t tail, head, way, first, last;
    std::int8_t direction;
    std::uint8_t reserved[3]{};
    std::uint64_t milliseconds;
};
struct Turn {
    std::uint64_t id, from, via, to;
    std::uint8_t kind, reserved[7]{};
};
static_assert(sizeof(Way) == 32 && sizeof(Arc) == 32 && sizeof(Turn) == 40, "cost_fact_widths");

class Graph {
    Output output_;
    Chunks ids_, anchor_ordinals_, xy_output_, flags_output_, geometry_, ways_, arcs_, turns_, invalid_, closures_output_;
    std::unique_ptr<car_node_index::Index> index_;
    std::vector<std::int32_t> xy_;
    std::vector<std::uint8_t> present_, flags_, roles_;
    std::vector<std::uint64_t> way_ids_, closures_, closed_nodes_;
    std::vector<std::uint32_t> arc_counts_, overflow_counts_;
    std::uint32_t selected_, anchors_;
    std::uint64_t expected_refs_, expected_ways_;
    std::uint64_t previous_way_ = 0;
    Bytes pending_;

    static void selected(void* user, std::uint64_t id, std::uint32_t ordinal, bool anchor) {
        auto& graph = *static_cast<Graph*>(user);
        graph.ids_.row(id);
        if (anchor) graph.anchor_ordinals_.row(ordinal);
    }
    void consume(const Record& record, const std::uint8_t* raw, std::uint32_t raw_size) {
        ++counts[record.kind];
        if (record.kind == 0) {
            if (!record.tags.empty()) {
                ++counts[26]; const auto flags = car_policy::node_flags(record.tags);
                counts[27] += bool(flags & 2); counts[28] += bool(flags & 1);
            }
            const auto node = index_->node(record.id);
            if (node == UINT32_MAX) return;
            need(!(present_[node/8] & (1U << (node%8))), "cost_duplicate_selected_coordinate");
            present_[node/8] |= 1U << (node%8); ++counts[16];
            xy_[2*node] = record.x; xy_[2*node+1] = record.y;
            const auto anchor = index_->anchor(record.id);
            if (anchor != UINT32_MAX) flags_[anchor] = car_policy::node_flags(record.tags) | 4;
            return;
        }
        if (record.kind == 1) {
            const auto policy = car_policy::way(record.tags); ++counts[32+policy.reason];
            if (policy.reason == car_policy::outside_profile) return;
            need(counts[16] == selected_, "cost_all_selected_coordinates_before_ways");
            need(record.refs.size() >= 2 && way_ids_.size() < 5000000 && static_cast<std::uint64_t>(record.id) > previous_way_, "cost_major_way_count_order");
            previous_way_ = record.id;
            const auto way = static_cast<std::uint32_t>(way_ids_.size());
            std::vector<std::uint32_t> nodes, anchors;
            nodes.reserve(record.refs.size()); anchors.reserve(record.refs.size());
            for (const auto id : record.refs) {
                const auto node = index_->node(id), anchor = index_->anchor(id);
                need(node != UINT32_MAX && (present_[node/8] & (1U << (node%8))), "cost_missing_native_coordinate");
                nodes.push_back(node); anchors.push_back(anchor); geometry_.row(node);
            }
            need(anchors.front() != UINT32_MAX && anchors.back() != UINT32_MAX, "cost_source_way_end_anchors");
            ++counts[5]; counts[6] = checked_add(counts[6], nodes.size());
            counts[18] = checked_add(counts[18], nodes.size());
            need(counts[18] < UINT32_MAX, "cost_geometry_offset_u32");
            const std::uint32_t flags = policy.directions | (std::uint32_t(policy.default_mask)<<2) | (std::uint32_t(policy.role)<<4) | (std::uint32_t(policy.reason)<<8);
            ways_.row(Way{static_cast<std::uint64_t>(record.id), policy.forward, policy.backward, flags, static_cast<std::uint32_t>(counts[18])});
            way_ids_.push_back(record.id); roles_.push_back(policy.role);
            arc_counts_.push_back(0); overflow_counts_.push_back(0);
            std::uint64_t forward = 0, backward = 0;
            std::uint32_t first = 0;
            bool distinct = false;
            for (std::uint32_t i = 1; i < nodes.size(); ++i) {
                const auto a = nodes[i-1], b = nodes[i]; const bool same = record.refs[i-1] == record.refs[i];
                distinct |= !same;
                if (policy.directions & 1) {
                    const auto cost = car_cost_math::primitive(xy_[2*a], xy_[2*a+1], xy_[2*b], xy_[2*b+1], policy.forward, same);
                    counts[22] = std::max(counts[22], cost); forward = car_cost_math::sum(forward, cost);
                }
                if (policy.directions & 2) {
                    const auto cost = car_cost_math::primitive(xy_[2*a], xy_[2*a+1], xy_[2*b], xy_[2*b+1], policy.backward, same);
                    counts[22] = std::max(counts[22], cost); backward = car_cost_math::sum(backward, cost);
                }
                if (anchors[i] == UINT32_MAX) continue;
                if (distinct) {
                    ++counts[7];
                    for (const auto direction : {1, -1}) {
                        const auto mask = direction == 1 ? 1 : 2;
                        if (!(policy.directions & mask)) continue;
                        const auto cost = direction == 1 ? forward : backward;
                        const auto tail = direction == 1 ? anchors[first] : anchors[i];
                        const auto head = direction == 1 ? anchors[i] : anchors[first];
                        arcs_.row(Arc{tail, head, way, first, i, static_cast<std::int8_t>(direction), {}, cost});
                        const bool overflow = car_cost_math::ticks(cost) >= 65535;
                        ++counts[8]; ++counts[42+policy.role]; counts[10] += overflow;
                        ++arc_counts_.back(); overflow_counts_.back() += overflow;
                        counts[23] = std::max(counts[23], cost);
                        need(counts[8] <= 16000000, "cost_arc_capacity");
                    }
                }
                first = i; forward = backward = 0; distinct = false;
            }
            need(first == nodes.size()-1, "cost_complete_source_way_partition");
            return;
        }
        car_policy::Rule rule;
        try { rule = car_policy::relation(record.tags, record.members); }
        catch (const std::runtime_error& error) {
            if (std::string_view(error.what()) != "unlocatable_unsupported_car_restriction") throw;
            need(counts[15] < 10000, "cost_invalid_source_record_cap"); ++counts[15];
            invalid_.row(raw_size); invalid_.append(raw, raw_size); return;
        }
        if (rule.status == car_policy::via_node) {
            ++counts[12]; turns_.row(Turn{static_cast<std::uint64_t>(record.id), rule.from, rule.via, rule.to, rule.kind, {}});
            need(counts[12] <= 2000000, "cost_turn_rule_capacity");
        } else if (rule.status == car_policy::closed_unsupported) {
            ++counts[13]; bool ways = false;
            for (const auto& member : record.members) if (member.kind == 1) {
                need(closures_.size() < 8000000, "cost_closure_way_capacity");
                closures_.push_back(member.ref); ++counts[14]; ways = true;
            }
            if (!ways) for (const auto& member : record.members) if (member.kind == 0) {
                need(closed_nodes_.size() < 8000000, "cost_closure_node_capacity"); closed_nodes_.push_back(member.ref);
            }
        }
    }
    void record(const std::uint8_t* bytes, std::uint32_t size) {
        Input in{bytes, size}; Record r;
        need(in.number(4) == 0x31465047, "cost_gpf_magic");
        r.kind = static_cast<std::uint8_t>(in.number(1)); r.visible = static_cast<std::uint8_t>(in.number(1));
        need(r.kind < 3 && in.number(2) == 0, "cost_gpf_kind_reserved");
        r.id = in.signed64(); r.version = in.signed64(); r.stamp = in.string();
        const auto tags = in.number(4); need(tags <= in.size/8, "cost_gpf_tag_count");
        for (std::uint64_t i = 0; i < tags; ++i) { const auto key = in.string(), value = in.string(); r.tags.emplace_back(key, value); }
        if (r.kind == 0) { r.x = in.signed32(); r.y = in.signed32(); }
        else {
            const auto count = in.number(4); need(count <= in.size/(r.kind == 1 ? 8 : 13), "cost_gpf_member_count");
            if (r.kind == 1) for (std::uint64_t i = 0; i < count; ++i) r.refs.push_back(in.signed64());
            else for (std::uint64_t i = 0; i < count; ++i) { const auto kind = static_cast<std::uint8_t>(in.number(1)); const auto ref = in.signed64(); const auto role = in.string(); r.members.push_back({kind, ref, role}); }
        }
        need(in.position == in.size, "cost_gpf_length"); consume(r, bytes, size);
    }
public:
    std::array<std::uint64_t, 64> counts{};
    bool running = false, attempted = false, source_complete = false, finished = false;
    Graph(const char* const* refs, std::uint32_t ref_parts, const char* const* tags, std::uint32_t tag_parts,
          const std::uint64_t* relation_nodes, std::uint64_t relation_count, std::uint64_t expected_refs,
          std::uint64_t expected_ways, std::uint64_t expected_tags, std::uint64_t maximum,
          std::uint32_t selected_nodes, std::uint32_t anchors, const char* output):
        ids_(output_, "ids"), anchor_ordinals_(output_, "anchors"), xy_output_(output_, "xy"),
        flags_output_(output_, "flags"), geometry_(output_, "geometry"), ways_(output_, "ways"),
        arcs_(output_, "arcs"), turns_(output_, "turns"), invalid_(output_, "invalid"), closures_output_(output_, "closures"),
        selected_(selected_nodes), anchors_(anchors), expected_refs_(expected_refs), expected_ways_(expected_ways) {
        need(output && strnlen(output, 4097) <= 4096 && selected_nodes <= 64000000 && anchors <= selected_nodes, "cost_configuration_bounds");
        struct stat state{}; need(::lstat(output, &state) == 0 && S_ISDIR(state.st_mode), "cost_existing_owned_directory");
        output_.root = output;
        index_ = car_node_index::prepare(refs, ref_parts, tags, tag_parts, relation_nodes, relation_count,
            expected_refs, expected_ways, expected_tags, maximum, selected_nodes, anchors, selected, this);
        ids_.finish(); anchor_ordinals_.finish();
        xy_.resize(2*static_cast<std::size_t>(selected_nodes)); present_.resize((static_cast<std::uint64_t>(selected_nodes)+7)/8);
        flags_.resize(anchors); counts[3] = selected_nodes; counts[4] = anchors; counts[17] = index_->bytes();
        way_ids_.reserve(expected_ways); roles_.reserve(expected_ways);
        arc_counts_.reserve(expected_ways); overflow_counts_.reserve(expected_ways);
    }
    void feed(const std::uint8_t* data, std::uint32_t size) {
        need(!finished && size <= 1048576 && pending_.size()+size <= 9437188, "cost_semantic_buffer_bound");
        pending_.insert(pending_.end(), data, data+size); std::size_t cursor = 0;
        while (pending_.size()-cursor >= 4) {
            const auto* p = pending_.data()+cursor;
            const std::uint32_t count = std::uint32_t(p[0]) | (std::uint32_t(p[1])<<8) | (std::uint32_t(p[2])<<16) | (std::uint32_t(p[3])<<24);
            need(count && count <= 8388608, "cost_semantic_frame_bound");
            if (pending_.size()-cursor-4 < count) break;
            record(p+4, count); cursor += 4+count;
        }
        if (cursor) pending_.erase(pending_.begin(), pending_.begin()+cursor);
    }
    void finish() {
        need(!running && source_complete && !finished && pending_.empty() && counts[16] == selected_, "cost_complete_source_required");
        need(counts[5] == expected_ways_ && counts[6] == expected_refs_, "cost_prepared_source_way_reference_totals");
        std::sort(closures_.begin(), closures_.end()); closures_.erase(std::unique(closures_.begin(), closures_.end()), closures_.end());
        counts[25] = closures_.size(); closures_output_.append(closures_.data(), closures_.size()*8);
        for (std::size_t i = 0; i < way_ids_.size(); ++i) if (!std::binary_search(closures_.begin(), closures_.end(), way_ids_[i])) {
            counts[9] += arc_counts_[i]; counts[11] += overflow_counts_[i]; counts[52+roles_[i]] += arc_counts_[i];
        }
        for (const auto node : closed_nodes_) {
            const auto anchor = index_->anchor(node);
            if (anchor != UINT32_MAX) flags_[anchor] |= 1;
        }
        xy_output_.append(xy_.data(), xy_.size()*4); flags_output_.append(flags_.data(), flags_.size());
        for (auto* stream : {&xy_output_, &flags_output_, &geometry_, &ways_, &arcs_, &turns_, &invalid_, &closures_output_}) stream->finish();
        counts[19] = counts[18]*4; counts[20] = counts[8]*32; counts[21] = way_ids_.size()*32;
        counts[30] = output_.bytes; counts[31] = 1; finished = true;
    }
};
thread_local std::unique_ptr<Graph> active;
struct Capture { Callback callback; void* user; std::string failure; };
int callback(void* user, std::uint32_t event, const std::uint8_t* data, std::uint32_t size) {
    auto& capture = *static_cast<Capture*>(user);
    try { if (event == 0) active->feed(data, size); return capture.callback(capture.user, event, data, size); }
    catch (const Failure& error) { capture.failure = error.message; }
    catch (const std::exception& error) { capture.failure = error.what(); }
    catch (...) { capture.failure = "cost_consumer_allocation_failure"; }
    return -1;
}
template<class Action> int capture(Action action, std::uint32_t mode, Callback outer, void* user, std::uint64_t* receipt, char* error, std::uint32_t size) noexcept {
    try {
        need(active && !active->running && !active->attempted && !active->source_complete && !active->finished && (mode == 0 || mode == 1) && outer && receipt && error && size && size <= 1024, "cost_capture_configuration");
        Capture capture{outer, user, {}}; active->running = true; active->attempted = true;
        const auto code = action(callback, &capture); active->running = false;
        if (!capture.failure.empty()) { error_text(error, size, capture.failure.c_str()); receipt[4] = 0; return -2; }
        active->source_complete = code == 0 && receipt[4] == 1; return code;
    } catch (const Failure& failure) { error_text(error, size, failure.message); }
    catch (...) { error_text(error, size, "cost_capture_failure"); }
    if (active) active->running = false;
    if (receipt) receipt[4] = 0;
    return -2;
}
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_car_graph_abi() noexcept { return 0x10000; }
extern "C" __attribute__((visibility("default")))
int gp_car_graph_begin(const char* const* refs, std::uint32_t ref_parts, const char* const* tags, std::uint32_t tag_parts,
    const std::uint64_t* relation_nodes, std::uint64_t relation_count, std::uint64_t expected_refs,
    std::uint64_t expected_ways, std::uint64_t expected_tags, std::uint64_t maximum,
    std::uint32_t selected, std::uint32_t anchors, const char* output, char* error, std::uint32_t size) noexcept {
    if (!error || !size || size > 1024) return -1; error[0] = 0;
    try {
        need(!car_cost_graph::active, "cost_reentrant_graph");
        car_cost_graph::active = std::make_unique<car_cost_graph::Graph>(refs, ref_parts, tags, tag_parts, relation_nodes, relation_count,
            expected_refs, expected_ways, expected_tags, maximum, selected, anchors, output); return 0;
    } catch (const Failure& failure) { error_text(error, size, failure.message); }
    catch (const std::exception& failure) { error_text(error, size, failure.what()); }
    catch (...) { error_text(error, size, "cost_configuration_failure"); } return -2;
}
extern "C" __attribute__((visibility("default")))
int gp_car_graph_finish(std::uint64_t* out, std::uint32_t words, char* error, std::uint32_t size) noexcept {
    if (!out || words != 64 || !error || !size || size > 1024) return -1; std::fill(out, out+words, 0); error[0] = 0;
    try { need(bool(car_cost_graph::active), "cost_missing_graph"); car_cost_graph::active->finish(); std::copy(car_cost_graph::active->counts.begin(), car_cost_graph::active->counts.end(), out); return 0; }
    catch (const Failure& failure) { error_text(error, size, failure.message); }
    catch (const std::exception& failure) { error_text(error, size, failure.what()); }
    catch (...) { error_text(error, size, "cost_finish_failure"); } return -2;
}
extern "C" __attribute__((visibility("default"))) void gp_car_graph_release() noexcept {
    if (!car_cost_graph::active || !car_cost_graph::active->running) car_cost_graph::active.reset();
}
extern "C" __attribute__((visibility("default")))
int gp_car_graph_frames(const std::uint8_t* data, std::uint64_t bytes, const char* snapshot, std::uint32_t limit,
    const std::uint64_t* limits, std::uint32_t limits_count, std::uint32_t mode, const std::int64_t* selected, std::uint32_t selected_count,
    Callback callback, void* user, std::uint64_t* receipt, std::uint32_t receipt_count, char* error, std::uint32_t error_size) noexcept {
    if (!receipt || receipt_count != receipt_size) return -1;
    return car_cost_graph::capture([&](Callback sink, void* state) { return gp_country_screen_frames(data, bytes, snapshot, limit, limits, limits_count, mode, selected, selected_count, sink, state, receipt, receipt_count, error, error_size); }, mode, callback, user, receipt, error, error_size);
}
extern "C" __attribute__((visibility("default")))
int gp_car_graph_pbf(const char* path, const char* snapshot, std::uint32_t limit, const std::uint64_t* limits,
    std::uint32_t limits_count, std::uint32_t mode, const std::int64_t* selected, std::uint32_t selected_count,
    Callback callback, void* user, std::uint64_t* receipt, std::uint32_t receipt_count, char* error, std::uint32_t error_size) noexcept {
    if (!receipt || receipt_count != receipt_size) return -1;
    return car_cost_graph::capture([&](Callback sink, void* state) { return gp_country_screen_pbf(path, snapshot, limit, limits, limits_count, mode, selected, selected_count, sink, state, receipt, receipt_count, error, error_size); }, mode, callback, user, receipt, error, error_size);
}
