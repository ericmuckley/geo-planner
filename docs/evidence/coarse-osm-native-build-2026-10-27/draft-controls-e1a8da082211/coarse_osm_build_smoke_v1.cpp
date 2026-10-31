// Minimal header/zlib/C-ABI qualification, not the importer or its validation contract.
#include <cstdint>
#include <osmium/handler.hpp>
#include <osmium/io/pbf_input.hpp>
#include <osmium/version.hpp>
#include <osmium/visitor.hpp>
#include <protozero/version.hpp>
#include <zlib.h>

struct Counts : osmium::handler::Handler {
    std::int64_t* values;
    explicit Counts(std::int64_t* output) : values(output) {}
    void node(const osmium::Node& node) {
        if (values[0] == 0) { values[3] = node.location().x(); values[4] = node.location().y(); }
        ++values[0];
    }
    void way(const osmium::Way&) { ++values[1]; }
    void relation(const osmium::Relation&) { ++values[2]; }
};

extern "C" __attribute__((visibility("default")))
int gp_pbf_counts(const char* path, std::int64_t* values) noexcept {
    if (!path || !values) return -2;
    for (unsigned i = 0; i != 5; ++i) values[i] = 0;
    try {
        osmium::io::Reader reader{path, osmium::osm_entity_bits::all};
        Counts counts{values};
        osmium::apply(reader, counts);
        reader.close();
        return 0;
    } catch (...) { return -1; }
}

extern "C" __attribute__((visibility("default")))
const char* gp_zlib_runtime() noexcept { return zlibVersion(); }

extern "C" __attribute__((visibility("default")))
const char* gp_zlib_header() noexcept { return ZLIB_VERSION; }
