// Offline native-ID membership/rank. No Python node map or disk coordinate lookup.
#pragma once
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace car_node_index {
inline void require(bool ok) {
    if (!ok) throw std::invalid_argument("car_node_index_bound_or_state");
}

class Index {
    std::vector<std::uint64_t> nodes_, anchors_;
    std::vector<std::uint32_t> node_prefix_, anchor_prefix_;
    std::uint64_t maximum_, previous_ = 0;
    std::uint32_t limit_, rows_ = 0, anchor_rows_ = 0;
    bool sealed_ = false;

    static void prefix(const std::vector<std::uint64_t>& bits, std::vector<std::uint32_t>& out) {
        out.resize((bits.size()+7)/8+1);
        std::uint32_t count = 0;
        for (std::size_t i = 0; i < bits.size(); ++i) {
            if (i%8 == 0) out[i/8] = count;
            count += __builtin_popcountll(bits[i]);
        }
        out.back() = count;
    }
    static std::uint32_t rank(const std::vector<std::uint64_t>& bits,
                              const std::vector<std::uint32_t>& sums, std::uint64_t id) {
        const auto word = id/64, shift = id%64;
        if (word >= bits.size() || !(bits[word] & (std::uint64_t{1} << shift))) return UINT32_MAX;
        auto value = sums[word/8];
        for (auto i = word/8*8; i < word; ++i) value += __builtin_popcountll(bits[i]);
        return value + __builtin_popcountll(bits[word] & ((std::uint64_t{1} << shift)-1));
    }

public:
    Index(std::uint64_t maximum, std::uint32_t count): maximum_(maximum), limit_(count) {
        require(maximum > 0 && maximum < (std::uint64_t{1} << 34) && count <= 64000000 && count <= maximum);
        nodes_.resize(maximum/64+1);
        anchors_.resize((static_cast<std::uint64_t>(count)+63)/64);
    }
    void append(std::uint64_t id, bool anchor) {
        require(!sealed_ && previous_ < id && id <= maximum_ && rows_ < limit_);
        nodes_[id/64] |= std::uint64_t{1} << (id%64);
        if (anchor) { anchors_[rows_/64] |= std::uint64_t{1} << (rows_%64); ++anchor_rows_; }
        previous_ = id; ++rows_;
    }
    void seal() {
        require(!sealed_ && rows_ == limit_);
        prefix(nodes_, node_prefix_); prefix(anchors_, anchor_prefix_);
        require(node_prefix_.back() == rows_ && anchor_prefix_.back() == anchor_rows_);
        sealed_ = true;
    }
    std::uint32_t node(std::uint64_t id) const {
        require(sealed_);
        return id && id <= maximum_ ? rank(nodes_, node_prefix_, id) : UINT32_MAX;
    }
    std::uint32_t anchor(std::uint64_t id) const {
        const auto ordinal = node(id);
        return ordinal == UINT32_MAX ? UINT32_MAX : rank(anchors_, anchor_prefix_, ordinal);
    }
    std::uint64_t bytes() const {
        return 8*(nodes_.capacity()+anchors_.capacity()) + 4*(node_prefix_.capacity()+anchor_prefix_.capacity());
    }
};
}
