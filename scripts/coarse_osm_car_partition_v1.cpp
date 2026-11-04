// Derive source-way contraction split occurrences from the sealed typed streams.
// Include the immutable checked reader/merge ABI; never edit its used producer.
#include "coarse_osm_topology_kernel_v1.cpp"

extern "C" __attribute__((visibility("default")))
std::uint32_t gp_car_partition_abi() noexcept { return 0x10000; }

extern "C" __attribute__((visibility("default")))
int gp_car_partition_splits(const char* const* ref_paths, std::uint32_t ref_parts,
    const char* const* tag_paths, std::uint32_t tag_parts, const std::uint64_t* relation_nodes, std::uint64_t relation_count,
    std::uint64_t expected_refs, std::uint64_t expected_ways, std::uint64_t expected_tags,
    std::uint64_t maximum_splits, const char* destination, std::uint64_t* receipt, std::uint32_t receipt_count,
    char* error, std::uint32_t error_size) noexcept {
    if (!receipt || receipt_count != 16) return -1;
    std::fill(receipt, receipt + 16, 0);
    return guarded([&] {
        need(ref_parts <= 256 && tag_parts <= 256 && (!ref_parts || ref_paths) && (!tag_parts || tag_paths), "partition_part_cap");
        need(relation_count <= 67108864 && expected_refs <= 509547029 && expected_ways <= expected_refs/2 && expected_tags <= 1606229364, "partition_input_rows");
        need(maximum_splits <= 8000000 && destination && strnlen(destination, 4097) <= 4096, "partition_output_cap_path");
        sorted_ids(relation_nodes, relation_count);
        TagStream tags(tag_paths, tag_parts, expected_tags);
        std::vector<std::unique_ptr<Reader>> readers;
        std::vector<Ref> previous(ref_parts);
        std::vector<bool> seen(ref_parts, false);
        std::priority_queue<Item, std::vector<Item>, Later> queue;
        const auto advance = [&](std::uint32_t part) {
            Ref row{};
            if (readers[part]->next(&row, sizeof(row))) {
                valid(row); need(!seen[part] || !less(row, previous[part]), "partition_reference_order");
                previous[part] = row; seen[part] = true; queue.push({row, part});
            }
        };
        for (std::uint32_t i = 0; i < ref_parts; ++i) { readers.push_back(std::make_unique<Reader>(ref_paths[i], 24)); advance(i); }
        std::uint64_t identity = 0, degree = 0;
        bool endpoint = false;
        std::vector<std::uint64_t> group_internal, splits;
        const auto finish = [&] {
            if (!identity) return;
            const bool tagged = tags.has(identity), relation = has(relation_nodes, relation_count, identity), junction = degree != 2;
            receipt[3] = add(receipt[3], 1);
            receipt[7] = add(receipt[7], tagged); receipt[8] = add(receipt[8], relation);
            receipt[9] = add(receipt[9], junction); receipt[10] = add(receipt[10], endpoint);
            receipt[14] = add(receipt[14], tagged || relation || junction);
            if (tagged || relation || junction || endpoint) {
                receipt[4] = add(receipt[4], 1);
                need(group_internal.size() <= maximum_splits - splits.size(), "partition_split_cap");
                splits.insert(splits.end(), group_internal.begin(), group_internal.end());
            }
        };
        while (!queue.empty()) {
            const auto item = queue.top(); queue.pop(); const auto& row = item.row;
            if (identity != row.node) { finish(); identity = row.node; degree = 0; endpoint = false; group_internal.clear(); }
            receipt[0] = add(receipt[0], 1); need(receipt[0] <= expected_refs, "partition_reference_cap");
            receipt[1] = add(receipt[1], row.degree); receipt[2] = add(receipt[2], row.flags);
            degree = add(degree, row.degree); endpoint |= row.flags != 0;
            if (!row.flags) { need(group_internal.size() < 1000000, "partition_node_group_cap"); group_internal.push_back(row.way); }
            advance(item.part);
        }
        finish(); tags.finish(); receipt[11] = tags.rows;
        need(receipt[0] == expected_refs && receipt[2] == 2*expected_ways && receipt[1] == 2*(expected_refs-expected_ways), "partition_whole_source_accounting");
        std::sort(splits.begin(), splits.end());
        receipt[5] = add(expected_ways, splits.size()); receipt[6] = expected_refs - expected_ways;
        receipt[12] = splits.size(); receipt[13] = splits.size()*8;
        const int fd = ::open(destination, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
        need(fd >= 0, "partition_fresh_output");
        const auto* bytes = reinterpret_cast<const unsigned char*>(splits.data());
        std::size_t written = 0;
        while (written < receipt[13]) {
            const auto count = ::write(fd, bytes + written, static_cast<std::size_t>(receipt[13] - written));
            if (count <= 0) { ::close(fd); throw Failure{"partition_output_write"}; }
            written += count;
        }
        struct stat result{};
        const bool ok = ::fstat(fd, &result) == 0 && S_ISREG(result.st_mode) && result.st_nlink == 1 && result.st_size == static_cast<off_t>(receipt[13]);
        const int closed = ::close(fd); need(ok && closed == 0, "partition_output_close"); receipt[15] = 1;
    }, error, error_size);
}
