// Generic static-car policy port. Full source validation belongs to the caller.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace car_policy {
using View = std::string_view;
using Tags = std::vector<std::pair<View, View>>;
inline constexpr std::array<View, 10> roles{{"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"}};
inline constexpr std::array<double, 10> defaults{{100, 40, 80, 40, 55, 35, 45, 30, 40, 30}};
inline constexpr std::array<View, 4> car_keys{{"motorcar", "motor_vehicle", "vehicle", "access"}};
inline constexpr std::array<View, 10> turns{{"no_left_turn", "no_right_turn", "no_straight_on", "no_u_turn", "no_entry", "no_exit", "only_left_turn", "only_right_turn", "only_straight_on", "only_u_turn"}};
inline void need(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
inline bool starts(View s, View prefix) { return s.size() >= prefix.size() && s.substr(0, prefix.size()) == prefix; }
inline bool ends(View s, View suffix) { return s.size() >= suffix.size() && s.substr(s.size() - suffix.size()) == suffix; }
inline std::optional<View> find(const Tags& tags, View key) {
    const auto i = std::lower_bound(tags.begin(), tags.end(), key, [](const auto& p, View k) { return p.first < k; });
    return i != tags.end() && i->first == key ? std::optional<View>(i->second) : std::nullopt;
}
inline View value(const Tags& tags, View key, View fallback = {}) { const auto v = find(tags, key); return v ? *v : fallback; }
inline bool one_of(View value, std::initializer_list<View> options) { return std::find(options.begin(), options.end(), value) != options.end(); }
inline bool allowed_value(View value) { return one_of(value, {"yes", "permissive", "designated"}); }
inline bool access(const Tags& tags, View direction = {}) {
    for (const auto key : car_keys) {
        if (!direction.empty()) { const auto v = find(tags, std::string(key) + ":" + std::string(direction)); if (v) return allowed_value(*v); }
        const auto v = find(tags, key); if (v) return allowed_value(*v);
    }
    return true;
}
inline bool conditional(const Tags& tags) {
    return std::any_of(tags.begin(), tags.end(), [](const auto& p) { return ends(p.first, ":conditional"); });
}
inline std::uint32_t scalar(View text, std::size_t& pos) {
    need(pos < text.size(), "truncated_utf8"); const auto lead = static_cast<unsigned char>(text[pos++]);
    if (lead < 128) return lead;
    unsigned count; std::uint32_t cp;
    if (lead >= 0xc2 && lead <= 0xdf) { count = 1; cp = lead & 31; }
    else if (lead >= 0xe0 && lead <= 0xef) { count = 2; cp = lead & 15; }
    else if (lead >= 0xf0 && lead <= 0xf4) { count = 3; cp = lead & 7; }
    else throw std::runtime_error("invalid_utf8");
    for (unsigned k = 0; k < count; ++k) {
        need(pos < text.size(), "truncated_utf8"); const auto next = static_cast<unsigned char>(text[pos++]);
        need((next & 0xc0) == 0x80, "invalid_utf8"); cp = (cp << 6) | (next & 63);
    }
    need((count != 1 || cp >= 0x80) && (count != 2 || cp >= 0x800) && (count != 3 || cp >= 0x10000) && cp <= 0x10ffff && !(cp >= 0xd800 && cp <= 0xdfff), "invalid_utf8_scalar");
    return cp;
}
inline bool whitespace(std::uint32_t cp) {
    return (cp >= 9 && cp <= 13) || (cp >= 28 && cp <= 32) || cp == 0x85 || cp == 0xa0 || cp == 0x1680 ||
           (cp >= 0x2000 && cp <= 0x200a) || cp == 0x2028 || cp == 0x2029 || cp == 0x202f || cp == 0x205f || cp == 0x3000;
}
inline View strip(View text) {
    std::size_t first = text.size(), last = 0;
    for (std::size_t pos = 0; pos < text.size();) { const auto start = pos; const auto cp = scalar(text, pos); if (!whitespace(cp)) { first = std::min(first, start); last = pos; } }
    return first == text.size() ? View{} : text.substr(first, last - first);
}
inline std::optional<double> speed(std::optional<View> raw, double fallback) {
    if (!raw) return fallback;
    const auto text = strip(*raw); std::size_t pos = 0;
    while (pos < text.size() && text[pos] >= '0' && text[pos] <= '9') ++pos;
    if (!pos) return {};
    if (pos < text.size() && text[pos] == '.') {
        const auto first = ++pos; while (pos < text.size() && text[pos] >= '0' && text[pos] <= '9') ++pos;
        if (first == pos) return {};
    }
    const auto number = std::string(text.substr(0, pos));
    while (pos < text.size()) { auto next = pos; if (!whitespace(scalar(text, next))) break; pos = next; }
    const auto unit = text.substr(pos); if (!one_of(unit, {"", "mph", "km/h", "kph"})) return {};
    const double parsed = std::strtod(number.c_str(), nullptr) * (unit == "mph" ? 1.609344 : 1.0);
    return parsed > 0 && parsed <= 160 ? std::optional<double>(parsed) : std::nullopt;
}

enum Reason : std::uint8_t { eligible, outside_profile, ferry, access_denied, area_ford_service, conditional_way, lane_access, oneway_unknown, speed_unknown, directional_access };
struct Way {
    Reason reason = eligible;
    std::uint8_t directions = 0, default_mask = 0, role = 255;
    double forward = 0, backward = 0;
};
inline Way way(const Tags& tags) {
    Way result; const auto role = value(tags, "highway"); const auto ri = std::find(roles.begin(), roles.end(), role);
    if (ri == roles.end()) { result.reason = outside_profile; return result; }
    result.role = static_cast<std::uint8_t>(ri - roles.begin());
    const auto reject = [&](Reason reason) { result.reason = reason; return result; };
    const auto ferry_tag = find(tags, "ferry");
    if (value(tags, "route") == "ferry" || (ferry_tag && !one_of(*ferry_tag, {"no", "false", "0"}))) return reject(ferry);
    if (!access(tags)) return reject(access_denied);
    if (value(tags, "area") == "yes" || !value(tags, "ford").empty() || one_of(value(tags, "service"), {"driveway", "parking_aisle"})) return reject(area_ford_service);
    for (const auto& p : tags) if (ends(p.first, ":conditional") || starts(p.first, "reversible") || starts(p.first, "restriction")) return reject(conditional_way);
    for (const auto& p : tags) if ((starts(p.first, "access") || starts(p.first, "vehicle") || starts(p.first, "motor") || starts(p.first, "oneway")) &&
                                   (ends(p.first, ":lanes") || p.first.find(":lanes:") != View::npos)) return reject(lane_access);
    auto oneway = find(tags, "oneway:motorcar"); if (!oneway) oneway = find(tags, "oneway:motor_vehicle"); if (!oneway) oneway = find(tags, "oneway");
    const auto direction = oneway ? *oneway : (role == "motorway" || one_of(value(tags, "junction"), {"roundabout", "circular"}) ? View("yes") : View("no"));
    if (!one_of(direction, {"yes", "1", "true", "no", "0", "false", "-1"})) return reject(oneway_unknown);
    auto f = find(tags, "maxspeed:forward"); if (!f) f = find(tags, "maxspeed");
    auto b = find(tags, "maxspeed:backward"); if (!b) b = find(tags, "maxspeed");
    const auto fs = speed(f, defaults[result.role]), bs = speed(b, defaults[result.role]);
    if (!fs || !bs) return reject(speed_unknown);
    result.default_mask = (!f ? 1 : 0) | (!b ? 2 : 0);
    if (direction != "-1" && access(tags, "forward")) { result.directions |= 1; result.forward = *fs; }
    if (one_of(direction, {"no", "0", "false", "-1"}) && access(tags, "backward")) { result.directions |= 2; result.backward = *bs; }
    if (!result.directions) result.reason = directional_access;
    return result;
}
inline bool barrier_open(const Tags& tags) {
    if (!one_of(value(tags, "barrier"), {"gate", "lift_gate", "border_control", "toll_booth"}) || conditional(tags)) return false;
    for (const auto& p : tags) {
        if (starts(p.first, "oneway") || starts(p.first, "reversible") || starts(p.first, "restriction")) return false;
        for (const auto key : car_keys) if (starts(p.first, std::string(key) + ":")) return false;
        if (starts(p.first, "maxwidth") || starts(p.first, "maxheight") || starts(p.first, "maxlength") || starts(p.first, "maxweight") || starts(p.first, "maxaxleload") || p.first == "width" || p.first == "height") return false;
    }
    if (value(tags, "locked", "no") != "no" || value(tags, "opening_hours", "24/7") != "24/7") return false;
    for (const auto key : car_keys) { const auto v = find(tags, key); if (v) return allowed_value(*v) && !(key == "access" && *v == "designated"); }
    return false;
}
inline std::uint8_t node_flags(const Tags& tags) {
    const bool blocked = !access(tags) || conditional(tags) || (!value(tags, "barrier").empty() && !barrier_open(tags));
    return (blocked ? 1 : 0) | (value(tags, "highway") == "traffic_signals" ? 2 : 0) | (!tags.empty() ? 4 : 0);
}

enum Status : std::uint8_t { unrelated, non_car, via_node, closed_unsupported };
struct Rule { Status status = unrelated; std::uint8_t kind = 255, reason = 0; std::uint64_t from = 0, via = 0, to = 0; };
template<class Members> Rule relation(const Tags& tags, const Members& members) {
    Rule result; const auto type = value(tags, "type"); if (!starts(type, "restriction")) return result;
    const auto colon = type.find(':'); const auto mode = colon == View::npos ? View{} : type.substr(colon + 1);
    const auto exceptions = value(tags, "except");
    for (std::size_t pos = 0; pos <= exceptions.size();) {
        const auto end = exceptions.find(';', pos); const auto token = strip(exceptions.substr(pos, end == View::npos ? end : end - pos));
        if (one_of(token, {"motorcar", "motor_vehicle", "vehicle"})) { result.status = non_car; return result; }
        if (end == View::npos) break; pos = end + 1;
    }
    if (!mode.empty() && !one_of(mode, {"motorcar", "motor_vehicle", "vehicle"})) { result.status = non_car; return result; }
    std::optional<View> kind;
    for (const auto key : {"restriction:motorcar", "restriction:motor_vehicle", "restriction:vehicle", "restriction"}) { kind = find(tags, key); if (kind) break; }
    bool car_conditional = false, other_mode = false;
    for (const auto& p : tags) {
        car_conditional |= one_of(p.first, {"restriction:conditional", "restriction:motorcar:conditional", "restriction:motor_vehicle:conditional", "restriction:vehicle:conditional"});
        other_mode |= starts(p.first, "restriction:");
    }
    if (!kind && !car_conditional && other_mode) { result.status = non_car; return result; }
    const auto ki = kind ? std::find(turns.begin(), turns.end(), *kind) : turns.end();
    std::uint32_t from_count = 0, to_count = 0, via_count = 0; bool has_location = false, via_way = false;
    for (const auto& member : members) {
        has_location |= member.kind < 2;
        if (member.kind == 1 && member.role == "from") { result.from = member.ref; ++from_count; }
        if (member.kind == 1 && member.role == "to") { result.to = member.ref; ++to_count; }
        if (member.kind == 0 && member.role == "via") { result.via = member.ref; ++via_count; }
        via_way |= member.kind == 1 && member.role == "via";
    }
    if (members.size() == 3 && from_count == 1 && to_count == 1 && via_count == 1 && ki != turns.end() && !conditional(tags) &&
        (result.from != result.to || ends(*kind, "u_turn") || ends(*kind, "straight_on"))) {
        result.status = via_node; result.kind = static_cast<std::uint8_t>(ki - turns.begin()); return result;
    }
    need(has_location, "unlocatable_unsupported_car_restriction"); result.status = closed_unsupported; result.reason = via_way ? 1 : 2; result.from = result.via = result.to = 0; return result;
}
} // namespace car_policy
