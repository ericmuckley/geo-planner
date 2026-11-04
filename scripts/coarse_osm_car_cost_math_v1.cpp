// Bounded pure cost kernel for reference equivalence; no source reader or graph.
#include "coarse_osm_car_cost_math_v1.hpp"
#include <cstring>

namespace {
template<class Action> int guarded(Action action, char* error, std::uint32_t size) noexcept {
    if (!error || !size || size > 1024) return -1;
    error[0] = 0;
    try { action(); return 0; }
    catch (const std::exception& failure) {
        const auto n = std::min<std::size_t>(size-1, std::strlen(failure.what()));
        std::memcpy(error, failure.what(), n); error[n] = 0;
    }
    catch (...) { error[0] = 0; }
    return -2;
}
}
extern "C" __attribute__((visibility("default")))
std::uint32_t gp_car_cost_math_abi() noexcept { return 0x10000; }

extern "C" __attribute__((visibility("default")))
int gp_car_cost_math_batch(const std::int32_t* xy, const double* speeds, const std::uint8_t* same,
    std::uint32_t count, std::uint64_t* out, char* error, std::uint32_t size) noexcept {
    return guarded([&] {
        car_cost_math::require(count <= 2000000 && (!count || (xy && speeds && same && out)));
        for (std::uint32_t i = 0; i < count; ++i) {
            car_cost_math::require(same[i] <= 1);
            out[i] = car_cost_math::primitive(xy[4*i], xy[4*i+1], xy[4*i+2], xy[4*i+3], speeds[i], same[i]);
        }
    }, error, size);
}

extern "C" __attribute__((visibility("default")))
int gp_car_cost_math_sum(const std::uint64_t* values, std::uint32_t count, std::uint64_t* out,
                        char* error, std::uint32_t size) noexcept {
    if (!out) return -1;
    out[0] = out[1] = 0;
    return guarded([&] {
        car_cost_math::require(count <= 2000000 && (!count || values));
        std::uint64_t total = 0;
        for (std::uint32_t i = 0; i < count; ++i) total = car_cost_math::sum(total, values[i]);
        out[0] = total; out[1] = car_cost_math::ticks(total);
    }, error, size);
}
