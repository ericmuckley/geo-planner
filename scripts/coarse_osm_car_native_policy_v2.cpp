// Reuse every V1 wire/metadata check; version only the unlocatable-record result.
#define gp_car_policy_abi gp_car_policy_v1_abi
#define gp_car_policy_frame gp_car_policy_v1_frame
#include "coarse_osm_car_native_policy_v1.cpp"
#undef gp_car_policy_abi
#undef gp_car_policy_frame

extern "C" __attribute__((visibility("default")))
std::uint32_t gp_car_policy_abi() noexcept { return 0x20000; }

extern "C" __attribute__((visibility("default")))
int gp_car_policy_frame(const std::uint8_t* bytes, std::uint32_t size, std::uint64_t* out,
                       std::uint32_t words, char* error, std::uint32_t error_size) noexcept {
    const auto code = gp_car_policy_v1_frame(bytes, size, out, words, error, error_size);
    if (code == -2 && std::strcmp(error, "unlocatable_unsupported_car_restriction") == 0) {
        // The complete V1 parser has validated this record. Its sole failure is
        // an applicable restriction without a direct node or way member.
        out[0] = 4; out[1] = 255; out[5] = 3; error[0] = 0;
        return 0;
    }
    return code;
}
