// Strict preclosed-ring adapter around the pinned cached libosmium assembler.
#include <osmium/area/assembler.hpp>
#include <osmium/builder/osm_object_builder.hpp>
#include <osmium/memory/buffer.hpp>
#include <osmium/osm/area.hpp>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

namespace {
struct Point { uint64_t id; int32_t x, y; };
static_assert(sizeof(Point)==16);
using Edge=std::tuple<uint8_t,uint64_t,uint64_t>;
using Callback=int (*)(void*,uint32_t,const void*,uint32_t);
void need(bool okay,const char* message) { if(!okay) throw std::runtime_error(message); }
Edge edge(uint8_t role,uint64_t a,uint64_t b) { return {role,std::min(a,b),std::max(a,b)}; }
void put32(std::vector<uint8_t>& out,uint32_t v) { for(int i=0;i<4;++i)out.push_back(uint8_t(v>>(i*8))); }
void put64(std::vector<uint8_t>& out,uint64_t v) { for(int i=0;i<8;++i)out.push_back(uint8_t(v>>(i*8))); }
void putpoint(std::vector<uint8_t>& out,const osmium::NodeRef& node) {
    put64(out,uint64_t(node.ref()));put32(out,uint32_t(node.location().x()));put32(out,uint32_t(node.location().y()));
}
struct OutputRing { uint8_t role; uint32_t parent; const osmium::NodeRefList* nodes; };
}

extern "C" __attribute__((visibility("default"))) uint32_t gp_water_area_abi() { return 0x10000; }

extern "C" __attribute__((visibility("default"))) int gp_water_area(
    const Point* points,uint64_t count,const uint64_t* offsets,const uint8_t* roles,uint32_t rings,
    Callback callback,void* user,char* error,uint32_t error_size) noexcept {
    try {
        need(points && offsets && roles && callback && rings>0 && rings<=100000 && count<=2000000,"area input/cap");
        need(offsets[0]==0 && offsets[rings]==count,"area offset partition");
        std::set<uint64_t> identities;
        std::set<std::pair<int32_t,int32_t>> positions;
        std::set<Edge> input_edges;
        std::map<uint64_t,std::pair<int32_t,int32_t>> source_points;
        uint32_t outer_count=0;
        for(uint32_t r=0;r<rings;++r) {
            const uint64_t first=offsets[r],end=offsets[r+1];
            need(first<end && end<=count && end-first>=4 && roles[r]<=1,"area ring fields/role");
            outer_count+=roles[r]==0;
            const auto& a=points[first];const auto& z=points[end-1];
            need(a.id==z.id && a.x==z.x && a.y==z.y,"area native-ID and coordinate closure");
            __int128 signed_area=0;
            for(uint64_t i=first;i<end-1;++i) {
                const auto& p=points[i];const auto& q=points[i+1];
                need(p.id>0 && p.id<(uint64_t(1)<<63),"area native node ID");
                need(p.x>=-1800000000 && p.x<=1800000000 && p.y>=-900000000 && p.y<=900000000,"area invalid E7 location");
                need(identities.insert(p.id).second,"area repeated/touching native node");
                need(positions.emplace(p.x,p.y).second,"area coincident positions, no identity merge");
                need(std::abs(int64_t(p.x)-q.x)<=1800000000,"area antimeridian edge requires separate policy");
                need(input_edges.insert(edge(roles[r],p.id,q.id)).second,"area duplicate source edge");
                source_points.emplace(p.id,std::make_pair(p.x,p.y));
                signed_area+=__int128(p.x)*q.y-__int128(q.x)*p.y;
            }
            need(signed_area!=0,"area zero signed area");
        }
        need(outer_count>0,"area no explicit outer ring");
        osmium::memory::Buffer ways{4096,osmium::memory::Buffer::auto_grow::yes};
        std::vector<size_t> way_offsets;
        for(uint32_t r=0;r<rings;++r) {
            way_offsets.push_back(ways.committed());
            {
                osmium::builder::WayBuilder builder{ways};builder.set_id(r+1);builder.set_version(1);
                osmium::builder::WayNodeListBuilder nodes{builder};
                for(uint64_t i=offsets[r];i<offsets[r+1];++i)nodes.add_node_ref(points[i].id,osmium::Location{points[i].x,points[i].y});
            }
            ways.commit();
        }
        std::vector<const osmium::Way*> members;
        for(auto offset:way_offsets)members.push_back(&ways.get<osmium::Way>(offset));
        osmium::memory::Buffer relation_buffer{4096,osmium::memory::Buffer::auto_grow::yes};
        {
            osmium::builder::RelationBuilder builder{relation_buffer};builder.set_id(1);builder.set_version(1);
            { osmium::builder::TagListBuilder tags{builder};tags.add_tag("type","multipolygon");tags.add_tag("natural","water"); }
            osmium::builder::RelationMemberListBuilder list{builder};
            for(uint32_t r=0;r<rings;++r) {
                const char* role=roles[r]==0?"outer":"inner";
                list.add_member(osmium::item_type::way,r+1,role,std::strlen(role));
            }
        }
        relation_buffer.commit();
        osmium::area::AssemblerConfig config;
        config.check_roles=true;config.ignore_invalid_locations=false;config.create_empty_areas=false;
        osmium::area::Assembler assembler{config};
        osmium::memory::Buffer output{4096,osmium::memory::Buffer::auto_grow::yes};
        need(assembler(relation_buffer.get<osmium::Relation>(0),members,output),"area kernel rejected geometry");
        const auto& stats=assembler.stats();
        need(!(stats.area_really_complex_case || stats.area_touching_rings_case || stats.duplicate_nodes ||
               stats.duplicate_segments || stats.duplicate_ways || stats.intersections || stats.no_way_in_mp_relation ||
               stats.open_rings || stats.overlapping_segments || stats.short_ways || stats.touching_rings ||
               stats.ways_in_multiple_rings || stats.wrong_role || stats.invalid_locations),"area kernel reports repair/problem/role mismatch");
        std::vector<OutputRing> result;uint32_t areas=0;
        for(const auto& area:output.select<osmium::Area>()) {
            ++areas;
            for(const auto& outer:area.outer_rings()) {
                const uint32_t parent=result.size();result.push_back({0,parent,&outer});
                for(const auto& inner:area.inner_rings(outer))result.push_back({1,parent,&inner});
            }
        }
        need(areas==1 && result.size()==rings,"area exact output object/ring count");
        std::set<Edge> output_edges;uint64_t output_count=0;
        for(const auto& ring:result) {
            const auto& nodes=*ring.nodes;
            need(nodes.size()>=4 && nodes.front().ref()==nodes.back().ref() && nodes.front().location()==nodes.back().location(),"area output native closure");
            __int128 signed_area=0;
            for(size_t i=0;i+1<nodes.size();++i) {
                const auto& p=nodes[i];const auto& q=nodes[i+1];
                const auto found=source_points.find(uint64_t(p.ref()));
                need(found!=source_points.end() && found->second==std::make_pair(p.location().x(),p.location().y()),"area every output source coordinate exact");
                need(output_edges.insert(edge(ring.role,p.ref(),q.ref())).second,"area repeated output edge");
                signed_area+=__int128(p.location().x())*q.location().y()-__int128(q.location().x())*p.location().y();
            }
            need((ring.role==0 && signed_area>0)||(ring.role==1 && signed_area<0),"area output orientation/zero area");
            output_count+=nodes.size();
        }
        need(input_edges==output_edges && output_count==count,"area exact native source-edge/role/reference coverage");
        // No output before every geometry, source-coordinate and source-edge check passes.
        std::vector<uint8_t> raw;raw.reserve(65536);
        for(const auto& ring:result) {
            raw.clear();put32(raw,ring.role);put32(raw,ring.parent);put64(raw,ring.nodes->size());
            need(callback(user,40,raw.data(),raw.size())==0,"area header callback refusal");raw.clear();
            for(const auto& node:*ring.nodes) {
                putpoint(raw,node);
                if(raw.size()==65536) { need(callback(user,41,raw.data(),raw.size())==0,"area point callback refusal");raw.clear(); }
            }
            if(!raw.empty())need(callback(user,41,raw.data(),raw.size())==0,"area point callback refusal");
        }
        if(error && error_size)error[0]=0;
        return 0;
    } catch(const std::exception& failure) {
        if(error && error_size) { std::strncpy(error,failure.what(),error_size-1);error[error_size-1]=0; }
        return -1;
    } catch(...) { if(error && error_size) { std::strncpy(error,"area unknown failure",error_size-1);error[error_size-1]=0; }return -2; }
}
