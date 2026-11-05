// Bounded pure-policy ABI for equivalence controls; no source reader or graph.
#include "coarse_osm_car_native_policy_v3.hpp"
#include <cstring>
#include <limits>

namespace {
using car_policy_conditional::View;
struct Input {
    const std::uint8_t* bytes;
    std::size_t size, pos = 0;
    std::uint64_t number(unsigned width) {
        car_policy_conditional::need(width <= size - pos, "truncated_policy_frame");
        std::uint64_t value = 0;
        for (unsigned k = 0; k < width; ++k) value |= std::uint64_t(bytes[pos++]) << (8 * k);
        return value;
    }
    View text() {
        const auto count = number(4);
        car_policy_conditional::need(count <= size - pos, "truncated_policy_string");
        const View result(reinterpret_cast<const char*>(bytes + pos), count);
        pos += count;
        for (std::size_t i = 0; i < result.size();) car_policy_conditional::scalar(result, i);
        return result;
    }
};
struct Member { std::uint8_t kind; std::uint64_t ref; View role; };
void error_text(char* out, std::uint32_t capacity, const char* message) {
    if (out && capacity) { const auto n = std::min<std::size_t>(capacity - 1, std::strlen(message)); std::memcpy(out, message, n); out[n] = 0; }
}
std::uint64_t bits(double n) { std::uint64_t value; std::memcpy(&value, &n, 8); return value; }
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_car_policy_abi() noexcept { return 0x30000; }
extern "C" __attribute__((visibility("default")))
int gp_car_policy_frame(const std::uint8_t* bytes, std::uint32_t size, std::uint64_t* out,
                        std::uint32_t output_words, char* error, std::uint32_t error_size) noexcept {
    if (!out || output_words != 8 || !error || !error_size || error_size > 1024) return -1;
    std::fill(out, out + 8, 0); error[0] = 0;
    try {
        car_policy_conditional::need(bytes && size >= 9 && size <= 4194304 && std::numeric_limits<double>::is_iec559, "policy_frame_bound");
        Input input{bytes, size}; car_policy_conditional::need(input.number(4) == 0x31504347, "policy_magic");
        const auto kind = input.number(1), count = input.number(4); car_policy_conditional::need(kind < 3 && count <= 65536, "policy_kind_tags");
        car_policy_conditional::Tags tags;
        for (std::uint64_t k = 0; k < count; ++k) {
            const auto key = input.text(), value = input.text();
            car_policy_conditional::need(k == 0 || tags.back().first < key, "policy_unique_sorted_tags"); tags.emplace_back(key, value);
        }
        std::vector<Member> members;
        if (kind == 2) {
            const auto total = input.number(4); car_policy_conditional::need(total <= 65536, "policy_member_cap");
            for (std::uint64_t k = 0; k < total; ++k) {
                const auto member_kind = input.number(1), ref = input.number(8); const auto role = input.text();
                car_policy_conditional::need(member_kind < 3 && ref > 0 && ref <= INT64_MAX, "policy_member_identity");
                members.push_back({static_cast<std::uint8_t>(member_kind), ref, role});
            }
        }
        car_policy_conditional::need(input.pos == input.size, "policy_trailing_bytes");
        if (kind == 0) out[0] = car_policy_conditional::node_flags(tags);
        else if (kind == 1) {
            const auto result = car_policy_conditional::way(tags);
            out[0] = result.reason; out[1] = result.directions; out[2] = result.default_mask; out[3] = result.role;
            out[4] = bits(result.forward); out[5] = bits(result.backward);
        } else {
            const auto result = car_policy_conditional::relation(tags, members);
            out[0] = result.status; out[1] = result.kind; out[2] = result.from; out[3] = result.via; out[4] = result.to; out[5] = result.reason;
        }
        return 0;
    } catch (const std::exception& failure) { error_text(error, error_size, failure.what()); }
    catch (...) { error_text(error, error_size, "policy_allocation_failure"); }
    std::fill(out, out + 8, 0); return -2;
}
