// Bounded payload codec only. Python retains SHA256 and the file/header contract.
#include <cstddef>
#include <cstdint>
#include <limits>

static_assert(sizeof(std::int64_t) == 8 && sizeof(std::int32_t) == 4, "C ABI widths");
namespace {
constexpr std::uint32_t max_rows = 4096;
constexpr std::uint64_t max_id = 0x7fffffffffffffffULL;

bool coordinates(std::int32_t x, std::int32_t y) noexcept {
    return x >= -1800000000 && x <= 1800000000 && y >= -900000000 && y <= 900000000;
}
void put32(std::uint8_t* out, std::int32_t value) noexcept {
    const auto bits = static_cast<std::uint32_t>(value);
    for (unsigned k = 0; k != 4; ++k) out[k] = static_cast<std::uint8_t>(bits >> (8 * k));
}
std::int32_t get32(const std::uint8_t* in) noexcept {
    std::uint32_t bits = 0;
    for (unsigned k = 0; k != 4; ++k) bits |= static_cast<std::uint32_t>(in[k]) << (8 * k);
    const std::int64_t value = bits <= 0x7fffffffU ? bits : static_cast<std::int64_t>(bits) - 0x100000000LL;
    return static_cast<std::int32_t>(value);
}
}

extern "C" __attribute__((visibility("default")))
std::uint32_t gp_delta_abi() noexcept { return 0x00010000U; }

extern "C" __attribute__((visibility("default")))
int gp_delta_encode(const std::int64_t* ids, const std::int32_t* xy, std::uint32_t rows,
                    std::uint8_t* out, std::uint32_t capacity, std::uint32_t* written) noexcept {
    if (!written) return -1;
    *written = 0;
    if (!ids || !xy || !out || rows == 0 || rows > max_rows) return -1;
    // Validate and size everything before writing any result.
    std::uint32_t required = rows * 8;
    std::uint64_t previous = 0;
    for (std::uint32_t k = 0; k != rows; ++k) {
        if (ids[k] <= 0 || static_cast<std::uint64_t>(ids[k]) <= previous ||
            !coordinates(xy[k * 2], xy[k * 2 + 1])) return -2;
        if (k) {
            std::uint64_t delta = static_cast<std::uint64_t>(ids[k]) - previous;
            do { ++required; delta >>= 7; } while (delta);
        }
        previous = static_cast<std::uint64_t>(ids[k]);
    }
    if (required > capacity) return -4;
    std::uint32_t position = 0;
    previous = static_cast<std::uint64_t>(ids[0]);
    for (std::uint32_t k = 0; k != rows; ++k) {
        if (k) {
            std::uint64_t delta = static_cast<std::uint64_t>(ids[k]) - previous;
            do {
                const auto byte = static_cast<std::uint8_t>(delta & 127);
                delta >>= 7;
                out[position++] = static_cast<std::uint8_t>(byte | (delta ? 128 : 0));
            } while (delta);
            previous = static_cast<std::uint64_t>(ids[k]);
        }
        put32(out + position, xy[k * 2]); put32(out + position + 4, xy[k * 2 + 1]);
        position += 8;
    }
    *written = position;
    return 0;
}

extern "C" __attribute__((visibility("default")))
int gp_delta_decode(const std::uint8_t* payload, std::uint32_t bytes, std::uint32_t rows,
                    std::int64_t first, std::int64_t last, std::int64_t* ids,
                    std::int32_t* xy, std::uint32_t capacity) noexcept {
    if (!payload || !ids || !xy || rows == 0 || rows > max_rows || capacity < rows) return -1;
    if (first <= 0 || last < first || bytes < rows * 8 + rows - 1 || bytes > rows * 8 + (rows - 1) * 9) return -2;
    std::uint32_t position = 0;
    std::uint64_t identity = static_cast<std::uint64_t>(first);
    for (std::uint32_t k = 0; k != rows; ++k) {
        if (k) {
            std::uint64_t delta = 0;
            unsigned used = 0;
            for (; used != 9; ++used) {
                if (position == bytes) return -3;
                const std::uint8_t byte = payload[position++];
                delta |= static_cast<std::uint64_t>(byte & 127) << (used * 7);
                if (!(byte & 128)) {
                    if (used && !(byte & 127)) return -3; // Non-shortest LEB128.
                    break;
                }
            }
            if (used == 9 || !delta || delta > max_id - identity) return -3;
            identity += delta;
        }
        if (bytes - position < 8) return -3;
        const auto x = get32(payload + position), y = get32(payload + position + 4);
        if (!coordinates(x, y)) return -2;
        ids[k] = static_cast<std::int64_t>(identity); xy[k * 2] = x; xy[k * 2 + 1] = y;
        position += 8;
    }
    if (position != bytes || identity != static_cast<std::uint64_t>(last)) return -3;
    return 0;
}
