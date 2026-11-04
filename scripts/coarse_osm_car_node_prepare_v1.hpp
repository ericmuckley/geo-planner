// Internal C++ construction interface; the public ABI belongs to the graph owner.
#pragma once
#include "coarse_osm_car_node_index_v1.hpp"
#include <memory>

namespace car_node_index {
using Sink = void(*)(void*, std::uint64_t, std::uint32_t, bool);
std::unique_ptr<Index> prepare(const char* const* references, std::uint32_t reference_parts,
    const char* const* tags, std::uint32_t tag_parts, const std::uint64_t* relation_nodes,
    std::uint64_t relation_count, std::uint64_t expected_refs, std::uint64_t expected_ways,
    std::uint64_t expected_tags, std::uint64_t maximum, std::uint32_t selected,
    std::uint32_t anchors, Sink sink, void* user);
}
