// Static conditional-speed prototype; legacy source rules remain shared.
#pragma once
#include "coarse_osm_car_native_policy_v1.hpp"

namespace car_policy_conditional {
using namespace car_policy;
inline bool ignored(View key) {
    if (!ends(key, ":conditional")) return false;
    key.remove_suffix(12);
    for (const auto direction : {View(":forward"), View(":backward")})
        if (ends(key, direction)) { key.remove_suffix(direction.size()); break; }
    for (const auto prefix : {View("maxspeed:"), View("oneway:")})
        if (starts(key, prefix)) { key.remove_prefix(prefix.size()); break; }
    return one_of(key, {"foot", "bicycle", "hgv"});
}
inline Tags scoped(const Tags& tags) {
    Tags result;
    for (const auto& item : tags) if (!ignored(item.first)) result.push_back(item);
    return result;
}
inline std::uint8_t node_flags(const Tags& tags) {
    return car_policy::node_flags(scoped(tags)) | (!tags.empty() ? 4 : 0);
}
inline std::optional<std::vector<double>> conditional_speeds(View text) {
    std::size_t characters = 0;
    for (std::size_t pos = 0; pos < text.size();) { scalar(text, pos); if (++characters > 65536) return {}; }
    if (text.empty()) return {};
    unsigned depth = 0; std::size_t start = 0; std::vector<View> clauses;
    for (std::size_t i = 0; i < text.size(); ++i) {
        const auto c = text[i];
        if (c == '\"' || c == '\'') return {};
        if (c == '(') { if (++depth > 8) return {}; }
        else if (c == ')') { if (!depth) return {}; --depth; }
        else if (c == ';' && !depth) { clauses.push_back(text.substr(start, i-start)); start = i+1; if (clauses.size() >= 64) return {}; }
    }
    if (depth) return {};
    clauses.push_back(text.substr(start)); std::vector<double> result;
    for (const auto clause : clauses) {
        const auto at = clause.find('@');
        if (at == View::npos || clause.find('@', at+1) != View::npos) return {};
        bool condition = false;
        for (std::size_t i = at+1; i < clause.size();) { const auto cp = scalar(clause, i); condition |= cp != '(' && cp != ')' && !whitespace(cp); }
        if (!condition) return {};
        const auto limit = speed(clause.substr(0, at), 0);
        if (!limit) return {};
        result.push_back(*limit);
    }
    return result;
}
inline Way way(const Tags& tags) {
    const auto filtered = scoped(tags); const auto original = car_policy::way(filtered);
    constexpr std::array<View,3> keys{{"maxspeed:conditional", "maxspeed:forward:conditional", "maxspeed:backward:conditional"}};
    std::array<std::vector<double>,3> limits; bool present = false;
    for (std::size_t i = 0; i < keys.size(); ++i) if (const auto text = find(filtered, keys[i])) {
        present = true; const auto parsed = conditional_speeds(*text); if (!parsed) return original; limits[i] = *parsed;
    }
    if (!present) return original;
    Tags base;
    for (const auto& item : filtered) if (std::find(keys.begin(), keys.end(), item.first) == keys.end()) base.push_back(item);
    auto result = car_policy::way(base); if (result.reason != eligible) return original;
    for (unsigned direction = 0; direction < 2; ++direction) if (result.directions & (1 << direction)) {
        auto& speed = direction == 0 ? result.forward : result.backward; const auto initial = speed;
        for (const auto limit : limits[0]) speed = std::min(speed, limit);
        for (const auto limit : limits[direction+1]) speed = std::min(speed, limit);
        if (speed < initial) result.default_mask &= ~(1 << direction);
    }
    return result;
}
template<class Members> Rule relation(const Tags& tags, const Members& members) {
    try { return car_policy::relation(tags, members); }
    catch (const std::runtime_error& error) {
        if (std::string_view(error.what()) != "unlocatable_unsupported_car_restriction") throw;
        Rule result; result.status = static_cast<Status>(4); result.reason = 3; return result;
    }
}
} // namespace car_policy_conditional
