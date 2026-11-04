// Preserve primitive source geometry and integer-ms costs before contraction.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace car_cost_math {
constexpr std::uint64_t maximum_ms = std::uint64_t{UINT32_MAX}*125;
inline void require(bool ok) {
    if (!ok) throw std::invalid_argument("car_cost_coordinate_speed_or_integer_bound");
}
inline std::uint64_t primitive(std::int32_t x1, std::int32_t y1, std::int32_t x2, std::int32_t y2,
                               double speed_kph, bool same_native_node) {
    require(x1 >= -1800000000 && x1 <= 1800000000 && x2 >= -1800000000 && x2 <= 1800000000 &&
            y1 >= -900000000 && y1 <= 900000000 && y2 >= -900000000 && y2 <= 900000000 &&
            std::isfinite(speed_kph) && speed_kph > 0 && speed_kph <= 160);
    if (same_native_node) { require(x1 == x2 && y1 == y2); return 0; }
    constexpr double radians = 3.141592653589793238462643383279502884/180;
    const double lon1 = (x1/1e7)*radians, lat1 = (y1/1e7)*radians,
                 lon2 = (x2/1e7)*radians, lat2 = (y2/1e7)*radians;
    const auto dy = std::sin((lat2-lat1)/2), dx = std::sin((lon2-lon1)/2);
    const auto h = dy*dy + std::cos(lat1)*std::cos(lat2)*(dx*dx);
    const auto meters = 6371008.8*2*std::asin(std::min(1.0, std::sqrt(h)));
    const auto value = std::ceil(meters*3600/speed_kph);
    require(std::isfinite(value) && value >= 0 && value <= maximum_ms);
    return std::max<std::uint64_t>(1, static_cast<std::uint64_t>(value));
}
inline std::uint64_t sum(std::uint64_t a, std::uint64_t b) {
    require(a <= maximum_ms && b <= maximum_ms-a); return a+b;
}
inline std::uint32_t ticks(std::uint64_t milliseconds) {
    require(milliseconds <= maximum_ms);
    return static_cast<std::uint32_t>((milliseconds+124)/125);
}
}
