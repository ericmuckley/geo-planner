// Reuse the sealed reader/merge/rank implementation in its own translation unit.
#include "coarse_osm_car_node_index_v1.cpp"
#include "coarse_osm_car_node_prepare_v1.hpp"

namespace car_node_index {
std::unique_ptr<Index> prepare(const char* const* references, std::uint32_t reference_parts,
    const char* const* tag_paths, std::uint32_t tag_parts, const std::uint64_t* relation_nodes,
    std::uint64_t relation_count, std::uint64_t expected_refs, std::uint64_t expected_ways,
    std::uint64_t expected_tags, std::uint64_t maximum, std::uint32_t selected,
    std::uint32_t expected_anchors, Sink sink, void* user) {
    try {
        need(reference_parts <= 256 && tag_parts <= 256 && (!reference_parts || references) && (!tag_parts || tag_paths) && sink, "prepare_part_cap");
        need(expected_refs <= 509547029 && expected_ways <= expected_refs/2 && expected_tags <= 1606229364 && relation_count <= 67108864, "prepare_row_cap");
        sorted_ids(relation_nodes, relation_count);
        auto index = std::make_unique<Index>(maximum, selected);
        TagStream tags(tag_paths, tag_parts, expected_tags);
        std::vector<std::unique_ptr<Reader>> readers;
        std::vector<Ref> previous(reference_parts);
        std::vector<bool> seen(reference_parts, false);
        std::priority_queue<Item, std::vector<Item>, Later> queue;
        const auto advance = [&](std::uint32_t part) {
            Ref row{};
            if (readers[part]->next(&row, sizeof(row))) {
                valid(row); need(!seen[part] || !less(row, previous[part]), "prepare_reference_order");
                previous[part] = row; seen[part] = true; queue.push({row, part});
            }
        };
        for (std::uint32_t i = 0; i < reference_parts; ++i) { readers.push_back(std::make_unique<Reader>(references[i], 24)); advance(i); }
        std::uint64_t id = 0, degree = 0, refs = 0, ends = 0, total_degree = 0;
        std::uint32_t ordinal = 0, anchors = 0;
        bool endpoint = false;
        const auto finish = [&] {
            if (!id) return;
            const bool anchor = tags.has(id) || has(relation_nodes, relation_count, id) || degree != 2 || endpoint;
            index->append(id, anchor); sink(user, id, ordinal, anchor);
            ++ordinal; anchors += anchor;
        };
        while (!queue.empty()) {
            const auto item = queue.top(); queue.pop(); const auto& row = item.row;
            if (row.node != id) { finish(); id = row.node; degree = 0; endpoint = false; }
            need(++refs <= expected_refs, "prepare_reference_count");
            degree = add(degree, row.degree); total_degree = add(total_degree, row.degree);
            endpoint |= row.flags != 0; ends += row.flags;
            advance(item.part);
        }
        finish(); tags.finish();
        need(refs == expected_refs && ends == 2*expected_ways && total_degree == 2*(expected_refs-expected_ways), "prepare_complete_incidence_accounting");
        need(ordinal == selected && anchors == expected_anchors, "prepare_selected_anchor_denominators");
        index->seal(); return index;
    } catch (const Failure& failure) { throw std::runtime_error(failure.message); }
}
}
