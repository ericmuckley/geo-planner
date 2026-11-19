// Explicit ordinary-car lane eligibility; every other source rule stays shared.
#pragma once
#include "coarse_osm_car_native_policy_v3.hpp"

namespace car_policy_lanes {
using namespace car_policy;
using car_policy_conditional::node_flags;
using car_policy_conditional::relation;

inline bool lane_key(View key) {
    return one_of(key, {"access:lanes", "vehicle:lanes", "motor_vehicle:lanes", "motorcar:lanes"});
}
inline std::optional<std::uint64_t> ordinary_columns(View text, unsigned count, bool hov) {
    if (text.size() > 4096) return {};
    std::uint64_t columns = 0; unsigned index = 0; std::size_t first = 0;
    for (;;) {
        const auto end = text.find('|', first);
        const auto value = text.substr(first, end == View::npos ? end : end-first);
        if (index >= count || !one_of(value, {"yes", "no", "designated", "psv"}) || (hov && value == "psv")) return {};
        if (value == "yes") columns |= std::uint64_t(1) << index;
        ++index;
        if (end == View::npos) break;
        first = end+1;
    }
    if (index != count) return {};
    return columns;
}
inline Way way(const Tags& tags) {
    const auto original = car_policy_conditional::way(tags);
    if (original.reason != lane_access) return original;
    const auto raw_count = find(tags, "lanes");
    if (!raw_count || raw_count->empty() || raw_count->size() > 2 || raw_count->front() == '0') return original;
    unsigned count = 0;
    for (const auto c : *raw_count) { if (c < '0' || c > '9') return original; count = 10*count+unsigned(c-'0'); }
    if (!count || count > 32) return original;
    auto oneway = find(tags, "oneway:motorcar");
    if (!oneway) oneway = find(tags, "oneway:motor_vehicle");
    if (!oneway) oneway = find(tags, "oneway");
    if (!oneway) oneway = (one_of(find(tags, "junction").value_or(""), {"roundabout", "circular"}) || find(tags, "highway") == View("motorway")) ? "yes" : "no";
    if (!one_of(*oneway, {"yes", "1", "true", "-1"}) || find(tags, "hov").value_or("yes") != "yes") return original;
    if (find(tags, "hov:minimum") && !find(tags, "hov:lanes")) return original;
    std::uint64_t common = (std::uint64_t(1) << count)-1; bool access_vector = false;
    Tags scoped;
    for (const auto& item : tags) {
        const auto key = item.first;
        if (one_of(key, {"lanes:forward", "lanes:backward", "lanes:both_ways", "lanes:reversible"})) return original;
        if (starts(key, "oneway:") && !one_of(key, {"oneway:motorcar", "oneway:motor_vehicle"})) return original;
        if (starts(key, "hov:") && !one_of(key, {"hov:lanes", "hov:minimum"})) return original;
        if (lane_key(key) || key == "hov:lanes") {
            const auto columns = ordinary_columns(item.second, count, key == "hov:lanes");
            if (!columns) return original;
            common &= *columns;
        }
        if (lane_key(key)) access_vector = true;
        else scoped.push_back(item);
    }
    if (!access_vector || !common) return original;
    const auto proposed = car_policy_conditional::way(scoped);
    if (proposed.reason != eligible || proposed.directions != (*oneway == "-1" ? 2 : 1)) return original;
    return proposed;
}
} // namespace car_policy_lanes
