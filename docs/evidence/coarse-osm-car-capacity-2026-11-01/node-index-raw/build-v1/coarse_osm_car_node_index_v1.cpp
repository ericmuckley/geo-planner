// Resource/lookup prototype on sealed typed incidences; never reads the PBF.
#include "coarse_osm_topology_kernel_v1.cpp"
#include "coarse_osm_car_node_index_v1.hpp"

extern "C" __attribute__((visibility("default")))
std::uint32_t gp_car_node_index_abi() noexcept { return 0x10000; }

extern "C" __attribute__((visibility("default")))
int gp_car_node_index_queries(const std::uint64_t* ids, const std::uint8_t* anchors, std::uint32_t count,
    std::uint64_t maximum, const std::uint64_t* queries, std::uint32_t total, std::uint64_t* out,
    char* error, std::uint32_t size) noexcept {
    return guarded([&] {
        need(count <= 2000000 && total <= 2000000 && (!count || (ids && anchors)) && (!total || (queries && out)), "index_control_buffers");
        car_node_index::Index index(maximum, count);
        for (std::uint32_t i = 0; i < count; ++i) {
            need(anchors[i] <= 1, "index_anchor_flag"); index.append(ids[i], anchors[i]);
        }
        index.seal();
        for (std::uint32_t i = 0; i < total; ++i)
            out[i] = index.node(queries[i]) | (std::uint64_t(index.anchor(queries[i])) << 32);
    }, error, size);
}

extern "C" __attribute__((visibility("default")))
int gp_car_node_index_probe(const char* const* ref_paths, std::uint32_t ref_parts,
    const char* const* tag_paths, std::uint32_t tag_parts,
    const std::uint64_t* relation_nodes, std::uint64_t relation_count,
    std::uint64_t expected_refs, std::uint64_t expected_ways, std::uint64_t expected_tags,
    std::uint64_t maximum, std::uint32_t selected, std::uint32_t expected_anchors,
    std::uint64_t* receipt, std::uint32_t words, char* error, std::uint32_t size) noexcept {
    if (!receipt || words != 8) return -1;
    std::fill(receipt, receipt+8, 0);
    return guarded([&] {
        need(ref_parts <= 256 && tag_parts <= 256 && (!ref_parts || ref_paths) && (!tag_parts || tag_paths), "index_part_cap");
        need(expected_refs <= 509547029 && expected_ways <= expected_refs/2 && expected_tags <= 1606229364 && relation_count <= 67108864, "index_rows_cap");
        sorted_ids(relation_nodes, relation_count);
        car_node_index::Index index(maximum, selected);
        // The second merge checks every real selected reference through rank;
        // the first uses only monotonically increasing source node groups.
        for (unsigned pass = 0; pass < 2; ++pass) {
            TagStream tags(tag_paths, tag_parts, expected_tags);
            std::vector<std::unique_ptr<Reader>> readers;
            std::vector<Ref> previous(ref_parts);
            std::vector<bool> seen(ref_parts, false);
            std::priority_queue<Item, std::vector<Item>, Later> queue;
            const auto advance = [&](std::uint32_t part) {
                Ref row{};
                if (readers[part]->next(&row, sizeof(row))) {
                    valid(row); need(!seen[part] || !less(row, previous[part]), "index_reference_order");
                    previous[part] = row; seen[part] = true; queue.push({row, part});
                }
            };
            for (std::uint32_t k = 0; k < ref_parts; ++k) { readers.push_back(std::make_unique<Reader>(ref_paths[k], 24)); advance(k); }
            std::uint64_t id = 0, degree = 0, refs = 0, ends = 0, total_degree = 0;
            std::uint32_t ordinal = 0, anchor_ordinal = 0;
            bool endpoint = false;
            const auto finish = [&] {
                if (!id) return;
                const bool anchor = tags.has(id) || has(relation_nodes, relation_count, id) || degree != 2 || endpoint;
                if (!pass) index.append(id, anchor);
                else {
                    need(index.node(id) == ordinal, "index_every_selected_ordinal");
                    need(index.anchor(id) == (anchor ? anchor_ordinal : UINT32_MAX), "index_every_anchor_ordinal");
                }
                ++ordinal; anchor_ordinal += anchor;
            };
            while (!queue.empty()) {
                const auto item = queue.top(); queue.pop(); const auto& row = item.row;
                if (id != row.node) { finish(); id = row.node; degree = 0; endpoint = false; }
                need(++refs <= expected_refs, "index_reference_count");
                if (pass) { need(index.node(row.node) == ordinal, "index_every_reference_lookup"); ++receipt[3]; }
                degree = add(degree, row.degree); total_degree = add(total_degree, row.degree);
                endpoint |= row.flags != 0; ends += row.flags;
                advance(item.part);
            }
            finish(); tags.finish();
            need(refs == expected_refs && ends == 2*expected_ways && total_degree == 2*(expected_refs-expected_ways), "index_complete_incidence_accounting");
            need(ordinal == selected && anchor_ordinal == expected_anchors, "index_selected_anchor_denominators");
            if (!pass) index.seal();
            receipt[0] = refs; receipt[1] = ordinal; receipt[2] = anchor_ordinal;
        }
        receipt[4] = index.bytes(); receipt[5] = maximum; receipt[6] = 2; receipt[7] = 1;
    }, error, size);
}
