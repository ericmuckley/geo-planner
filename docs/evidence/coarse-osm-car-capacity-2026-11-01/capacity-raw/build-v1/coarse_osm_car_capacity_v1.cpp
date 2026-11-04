// Compose the immutable source validator with a native consumer of its sealed GPF stream.
// The original callbacks/receipts/semantic bytes remain unchanged.
#include "coarse_osm_topology_source_v1.cpp"
#include "coarse_osm_car_native_policy_v1.hpp"
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>

namespace car_capacity {
constexpr std::uint64_t mib = 1048576;
struct WayFact {
    std::uint64_t id, first, last;
    std::uint32_t segments, flags;
};
static_assert(sizeof(WayFact) == 32, "car_way_fact_width");

class Census {
    std::vector<std::uint64_t> splits_, closures_;
    std::vector<std::uint8_t> presence_;
    std::vector<WayFact> ways_;
    std::vector<std::uint64_t> unlocatable_;
    std::string destination_;
    std::size_t split_cursor_ = 0;
    std::uint64_t max_node_, output_bytes_ = 0;
    Bytes pending_;

    void write_file(const std::string& name, const void* data, std::size_t size) {
        need(size <= 64*mib && size <= 240*mib-output_bytes_, "car_output_capacity");
        const auto path = destination_ + "/" + name;
        const int fd = ::open(path.c_str(), O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW, 0600);
        need(fd >= 0, "car_fresh_output");
        std::size_t done = 0;
        while (done < size) {
            const auto count = ::write(fd, static_cast<const unsigned char*>(data)+done, size-done);
            if (count <= 0) { ::close(fd); throw Failure{"car_output_write"}; }
            done += count;
        }
        struct stat state{};
        const bool ok = ::fstat(fd, &state) == 0 && S_ISREG(state.st_mode) && state.st_nlink == 1 && state.st_size == static_cast<off_t>(size);
        const int closed = ::close(fd); need(ok && closed == 0, "car_output_close"); output_bytes_ += size;
    }
    void consume(const Record& r) {
        ++counts[r.kind];
        if (r.kind == 0) {
            need(static_cast<std::uint64_t>(r.id) <= max_node_, "car_presence_id_bound");
            presence_[r.id/8] |= 1U << (r.id%8);
            counts[30] = std::max(counts[30], static_cast<std::uint64_t>(r.id));
            if (!r.tags.empty()) {
                ++counts[24]; const auto flags = car_policy::node_flags(r.tags);
                counts[25] += bool(flags & 2); counts[26] += bool(flags & 1);
            }
            return;
        }
        if (r.kind == 1) {
            const auto policy = car_policy::way(r.tags); ++counts[32+policy.reason];
            if (policy.reason == car_policy::outside_profile) return;
            need(r.refs.size() >= 2 && ways_.size() < 5000000, "car_major_way_capacity");
            need(split_cursor_ == splits_.size() || splits_[split_cursor_] >= static_cast<std::uint64_t>(r.id), "car_orphan_partition_way");
            std::uint64_t segments = 1, zero = 0;
            while (split_cursor_ < splits_.size() && splits_[split_cursor_] == static_cast<std::uint64_t>(r.id)) { ++segments; ++split_cursor_; ++counts[6]; }
            for (std::size_t i = 0; i < r.refs.size(); ++i) {
                const auto node = static_cast<std::uint64_t>(r.refs[i]);
                need(node <= max_node_ && (presence_[node/8] & (1U << (node%8))), "car_missing_selected_source_node");
                if (i && r.refs[i] == r.refs[i-1]) ++zero;
            }
            need(zero <= segments && segments <= UINT32_MAX, "car_nonzero_partition_accounting");
            ++counts[3]; counts[4] = checked_add(counts[4], r.refs.size()); counts[5] = checked_add(counts[5], r.refs.size()-1);
            counts[7] = checked_add(counts[7], segments); counts[8] = checked_add(counts[8], zero); segments -= zero;
            counts[9] = checked_add(counts[9], segments);
            const std::uint64_t directions = bool(policy.directions & 1) + bool(policy.directions & 2);
            const std::uint64_t defaults = bool(policy.directions & policy.default_mask & 1) + bool(policy.directions & policy.default_mask & 2);
            const auto arcs = segments*directions;
            counts[10] = checked_add(counts[10], arcs); counts[42+policy.role] = checked_add(counts[42+policy.role], arcs);
            counts[21] += directions != 0; counts[22] += directions; counts[23] += defaults; counts[63] = checked_add(counts[63], segments*defaults);
            const std::uint32_t flags = policy.directions | (std::uint32_t(policy.default_mask)<<2) | (std::uint32_t(policy.role)<<4) | (std::uint32_t(policy.reason)<<8);
            ways_.push_back({static_cast<std::uint64_t>(r.id), static_cast<std::uint64_t>(r.refs.front()), static_cast<std::uint64_t>(r.refs.back()), static_cast<std::uint32_t>(segments), flags});
            return;
        }
        car_policy::Rule rule;
        try { rule = car_policy::relation(r.tags, r.members); }
        catch (const std::runtime_error& error) {
            if (std::string_view(error.what()) != "unlocatable_unsupported_car_restriction") throw;
            need(unlocatable_.size() < 10000, "car_unlocatable_evidence_cap"); unlocatable_.push_back(r.id); ++counts[19]; return;
        }
        if (rule.status == car_policy::unrelated) ++counts[18];
        else if (rule.status == car_policy::non_car) ++counts[17];
        else if (rule.status == car_policy::via_node) ++counts[16];
        else {
            ++counts[12]; bool has_way = false;
            for (const auto& member : r.members) if (member.kind == 1) {
                need(closures_.size() < 8000000, "car_closure_occurrence_cap"); closures_.push_back(member.ref); ++counts[13]; has_way = true;
            }
            counts[20] += !has_way;
        }
    }
    void record(const std::uint8_t* bytes, std::size_t size) {
        Input in{bytes, size}; Record r;
        need(in.number(4) == 0x31465047, "car_gpf_magic");
        r.kind = static_cast<std::uint8_t>(in.number(1)); r.visible = static_cast<std::uint8_t>(in.number(1));
        need(r.kind < 3 && in.number(2) == 0, "car_gpf_kind_reserved");
        r.id = in.signed64(); r.version = in.signed64(); r.stamp = in.string();
        const auto tags = in.number(4); need(tags <= in.size/8, "car_gpf_tag_count");
        for (std::uint64_t k = 0; k < tags; ++k) { const auto key = in.string(), value = in.string(); r.tags.emplace_back(key, value); }
        if (r.kind == 0) { r.x = in.signed32(); r.y = in.signed32(); }
        else {
            const auto count = in.number(4); need(count <= in.size/(r.kind == 1 ? 8 : 13), "car_gpf_member_count");
            if (r.kind == 1) for (std::uint64_t k = 0; k < count; ++k) r.refs.push_back(in.signed64());
            else for (std::uint64_t k = 0; k < count; ++k) { const auto kind = static_cast<std::uint8_t>(in.number(1)); const auto ref = in.signed64(); const auto role = in.string(); r.members.push_back({kind, ref, role}); }
        }
        need(in.position == in.size, "car_gpf_length"); consume(r);
    }
public:
    std::array<std::uint64_t, 64> counts{};
    bool running = false, attempted = false, source_complete = false, finished = false;
    Census(const std::uint64_t* splits, std::uint64_t count, std::uint64_t maximum, const char* output): max_node_(maximum) {
        need(count <= 8000000 && (!count || splits) && maximum > 0 && maximum <= 14319708500ULL && output && strnlen(output, 4097) <= 4096, "car_census_configuration");
        const std::uint16_t one = 1; need(*reinterpret_cast<const unsigned char*>(&one) == 1, "car_little_endian");
        struct stat state{}; need(::lstat(output, &state) == 0 && S_ISDIR(state.st_mode), "car_existing_owned_directory");
        destination_ = output;
        for (std::uint64_t i = 0; i < count; ++i) need(splits[i] > 0 && splits[i] <= INT64_MAX && (!i || splits[i-1] <= splits[i]), "car_sorted_partition_way_ids");
        if (count) splits_.assign(splits, splits+count);
        presence_.resize(maximum/8+1, 0);
    }
    void feed(const std::uint8_t* data, std::uint32_t size) {
        need(!finished && size <= 1048576 && pending_.size()+size <= 9437188, "car_semantic_buffer_bound");
        pending_.insert(pending_.end(), data, data+size); std::size_t cursor = 0;
        while (pending_.size()-cursor >= 4) {
            const auto* p = pending_.data()+cursor;
            const std::uint32_t count = std::uint32_t(p[0]) | (std::uint32_t(p[1])<<8) | (std::uint32_t(p[2])<<16) | (std::uint32_t(p[3])<<24);
            need(count > 0 && count <= 8388608, "car_semantic_frame_bound");
            if (pending_.size()-cursor-4 < count) break;
            record(p+4, count); cursor += 4+count;
        }
        if (cursor) pending_.erase(pending_.begin(), pending_.begin()+cursor);
    }
    void finish() {
        need(!running && source_complete && !finished && pending_.empty() && split_cursor_ == splits_.size(), "car_complete_source_and_partitions_required");
        std::sort(closures_.begin(), closures_.end()); closures_.erase(std::unique(closures_.begin(), closures_.end()), closures_.end()); counts[14] = closures_.size();
        for (const auto& fact : ways_) {
            const bool closed = std::binary_search(closures_.begin(), closures_.end(), fact.id); counts[15] += closed;
            const std::uint64_t directions = bool(fact.flags & 1) + bool(fact.flags & 2);
            const auto arcs = closed ? 0 : fact.segments*directions;
            counts[11] = checked_add(counts[11], arcs); counts[52+((fact.flags>>4)&15)] = checked_add(counts[52+((fact.flags>>4)&15)], arcs);
            counts[62] += !closed && directions;
        }
        constexpr std::size_t rows = 524288;
        for (std::size_t i = 0; i < ways_.size(); i += rows) {
            char name[32]; std::snprintf(name, sizeof(name), "ways-%04zu.bin", i/rows);
            write_file(name, ways_.data()+i, std::min(rows, ways_.size()-i)*sizeof(WayFact));
        }
        write_file("unsupported-member-ways.u64", closures_.data(), closures_.size()*8);
        write_file("unlocatable-restrictions.u64", unlocatable_.data(), unlocatable_.size()*8);
        counts[28] = ways_.size(); counts[29] = ways_.size()*sizeof(WayFact); counts[31] = 1; finished = true;
    }
};
thread_local std::unique_ptr<Census> active;
struct Capture { Callback callback; void* user; std::string failure; };
int callback(void* user, std::uint32_t event, const std::uint8_t* data, std::uint32_t size) {
    auto& capture = *static_cast<Capture*>(user);
    try { if (event == 0) active->feed(data, size); return capture.callback(capture.user, event, data, size); }
    catch (const Failure& error) { capture.failure = error.message; }
    catch (const std::exception& error) { capture.failure = error.what(); }
    catch (...) { capture.failure = "car_consumer_allocation_failure"; }
    return -1;
}
template<class Action> int capture(Action action, std::uint32_t mode, Callback outer, void* user, std::uint64_t* receipt, char* error, std::uint32_t size) noexcept {
    try {
        need(active && !active->running && !active->attempted && !active->source_complete && !active->finished && (mode == 0 || mode == 1) && outer && receipt && error && size && size <= 1024, "car_active_capture_configuration");
        Capture capture{outer, user, {}}; active->running = true; active->attempted = true;
        const auto code = action(callback, &capture); active->running = false;
        if (!capture.failure.empty()) { error_text(error, size, capture.failure.c_str()); receipt[4] = 0; return -2; }
        active->source_complete = code == 0 && receipt[4] == 1; return code;
    } catch (const Failure& failure) { error_text(error, size, failure.message); }
    catch (...) { error_text(error, size, "car_capture_failure"); }
    if (active) active->running = false;
    if (receipt) receipt[4] = 0;
    return -2;
}
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_car_capacity_abi() noexcept { return 0x10000; }
extern "C" __attribute__((visibility("default")))
int gp_car_capacity_begin(const std::uint64_t* splits, std::uint64_t count, std::uint64_t maximum, const char* output, char* error, std::uint32_t size) noexcept {
    if (!error || !size || size > 1024) return -1; error[0] = 0;
    try { need(!car_capacity::active, "car_reentrant_capacity"); car_capacity::active = std::make_unique<car_capacity::Census>(splits, count, maximum, output); return 0; }
    catch (const Failure& failure) { error_text(error, size, failure.message); }
    catch (const std::exception& failure) { error_text(error, size, failure.what()); }
    catch (...) { error_text(error, size, "car_configuration_failure"); } return -2;
}
extern "C" __attribute__((visibility("default")))
int gp_car_capacity_finish(std::uint64_t* out, std::uint32_t words, char* error, std::uint32_t size) noexcept {
    if (!out || words != 64 || !error || !size || size > 1024) return -1; std::fill(out, out+words, 0); error[0] = 0;
    try { need(bool(car_capacity::active), "car_missing_capacity"); car_capacity::active->finish(); std::copy(car_capacity::active->counts.begin(), car_capacity::active->counts.end(), out); return 0; }
    catch (const Failure& failure) { error_text(error, size, failure.message); }
    catch (const std::exception& failure) { error_text(error, size, failure.what()); }
    catch (...) { error_text(error, size, "car_finish_failure"); } return -2;
}
extern "C" __attribute__((visibility("default"))) void gp_car_capacity_release() noexcept {
    if (!car_capacity::active || !car_capacity::active->running) car_capacity::active.reset();
}
extern "C" __attribute__((visibility("default")))
int gp_car_capacity_frames(const std::uint8_t* data, std::uint64_t bytes, const char* snapshot, std::uint32_t limit,
    const std::uint64_t* limits, std::uint32_t limits_count, std::uint32_t mode, const std::int64_t* selected, std::uint32_t selected_count,
    Callback callback, void* user, std::uint64_t* receipt, std::uint32_t receipt_count, char* error, std::uint32_t error_size) noexcept {
    if (!receipt || receipt_count != receipt_size) return -1;
    return car_capacity::capture([&](Callback sink, void* state) { return gp_country_screen_frames(data, bytes, snapshot, limit, limits, limits_count, mode, selected, selected_count, sink, state, receipt, receipt_count, error, error_size); }, mode, callback, user, receipt, error, error_size);
}
extern "C" __attribute__((visibility("default")))
int gp_car_capacity_pbf(const char* path, const char* snapshot, std::uint32_t limit, const std::uint64_t* limits,
    std::uint32_t limits_count, std::uint32_t mode, const std::int64_t* selected, std::uint32_t selected_count,
    Callback callback, void* user, std::uint64_t* receipt, std::uint32_t receipt_count, char* error, std::uint32_t error_size) noexcept {
    if (!receipt || receipt_count != receipt_size) return -1;
    return car_capacity::capture([&](Callback sink, void* state) { return gp_country_screen_pbf(path, snapshot, limit, limits, limits_count, mode, selected, selected_count, sink, state, receipt, receipt_count, error, error_size); }, mode, callback, user, receipt, error, error_size);
}
