// Typed coordinate/way tables for saved water geometry, without a source reader.
#include "coarse_osm_water_area_v1.cpp"
#include <limits>

namespace {
struct Catalog {
    uint64_t expected_nodes=0,expected_ways=0,expected_refs=0,tagged=0;
    bool points_sealed=false,ways_sealed=false,failed=false;
    std::vector<Point> points;
    std::vector<uint64_t> way_ids,offsets,refs;
    std::vector<uint8_t> water;
};
Catalog catalog;
uint32_t read32(const uint8_t*& cursor,const uint8_t* end) {
    need(end-cursor>=4,"catalog truncated u32");uint32_t result=0;
    for(unsigned i=0;i<4;++i)result|=uint32_t(*cursor++)<<(8*i);return result;
}
uint64_t read64(const uint8_t*& cursor,const uint8_t* end) {
    need(end-cursor>=8,"catalog truncated u64");uint64_t result=0;
    for(unsigned i=0;i<8;++i)result|=uint64_t(*cursor++)<<(8*i);return result;
}
std::string read_string(const uint8_t*& cursor,const uint8_t* end) {
    const auto count=read32(cursor,end);need(uint64_t(end-cursor)>=count,"catalog truncated string");
    std::string result(reinterpret_cast<const char*>(cursor),count);cursor+=count;return result;
}
const Point& lookup(uint64_t identity) {
    const auto found=std::lower_bound(catalog.points.begin(),catalog.points.end(),identity,[](const Point& p,uint64_t id){return p.id<id;});
    need(found!=catalog.points.end() && found->id==identity,"catalog missing node geometry");return *found;
}
size_t way_rank(uint64_t identity) {
    const auto found=std::lower_bound(catalog.way_ids.begin(),catalog.way_ids.end(),identity);
    need(found!=catalog.way_ids.end() && *found==identity,"catalog missing member way");return found-catalog.way_ids.begin();
}
template<class F> int guarded(F function,char* error,uint32_t size) noexcept {
    try { need(!catalog.failed,"catalog failed state requires release");function();if(error && size)error[0]=0;return 0; }
    catch(const std::exception& failure) { catalog.failed=true;if(error && size){std::strncpy(error,failure.what(),size-1);error[size-1]=0;}return -1; }
    catch(...) { catalog.failed=true;if(error && size){std::strncpy(error,"catalog unknown failure",size-1);error[size-1]=0;}return -2; }
}
}

extern "C" __attribute__((visibility("default"))) uint32_t gp_water_catalog_abi() {return 0x10000;}
extern "C" __attribute__((visibility("default"))) void gp_water_catalog_release() noexcept {catalog=Catalog{};}
extern "C" __attribute__((visibility("default"))) int gp_water_catalog_begin(uint64_t nodes,uint64_t ways,uint64_t refs,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(catalog.expected_nodes==0 && nodes>0 && nodes<=101738006 && ways>0 && ways<=2829193 && refs>0 && refs<=104806243,"catalog fresh state/count caps");
        catalog.expected_nodes=nodes;catalog.expected_ways=ways;catalog.expected_refs=refs;
        // Only coordinates coexist with the old decoder's temporary ID vector.
        catalog.points.reserve(nodes);
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_catalog_points(const Point* points,uint32_t count,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(points && count>0 && count<=65536 && catalog.expected_nodes && !catalog.points_sealed && catalog.points.size()+count<=catalog.expected_nodes,"catalog point chunk/state");
        for(uint32_t i=0;i<count;++i) {
            const auto& p=points[i];
            need(p.id>0 && p.id<(uint64_t(1)<<63) && (catalog.points.empty() || catalog.points.back().id<p.id),"catalog ordered unique native node IDs");
            need(p.x>=-1800000000 && p.x<=1800000000 && p.y>=-900000000 && p.y<=900000000,"catalog exact valid E7 coordinates");
            catalog.points.push_back(p);
        }
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_catalog_points_seal(Callback callback,void* user,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(!catalog.points_sealed && catalog.points.size()==catalog.expected_nodes && callback,"catalog complete points before seal");
        std::vector<uint8_t> raw;raw.reserve(65536);
        for(const auto& p:catalog.points) {
            put64(raw,p.id);put32(raw,uint32_t(p.x));put32(raw,uint32_t(p.y));
            if(raw.size()==65536) {need(callback(user,32,raw.data(),raw.size())==0,"catalog coordinate audit callback");raw.clear();}
        }
        if(!raw.empty())need(callback(user,32,raw.data(),raw.size())==0,"catalog coordinate audit callback");
        catalog.points_sealed=true;
        // Caller must release the independent decoder ID vector before appending ways.
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_catalog_way(const uint8_t* raw,uint32_t bytes,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(raw && bytes>=28 && bytes<=8388608 && catalog.points_sealed && !catalog.ways_sealed && catalog.way_ids.size()<catalog.expected_ways,"catalog way frame/state/cap");
        const uint8_t* cursor=raw;const auto* end=raw+bytes;
        need(read32(cursor,end)==0x31465047 && *cursor++==1 && *cursor++==1 && *cursor++==0 && *cursor++==0,"catalog GPF way kind/visibility/reserved");
        const auto identity=read64(cursor,end);need(identity>0 && identity<(uint64_t(1)<<63) && (catalog.way_ids.empty() || catalog.way_ids.back()<identity),"catalog strictly ordered way IDs");
        const auto version=read64(cursor,end);need(version>0 && version<(uint64_t(1)<<63),"catalog way version");read_string(cursor,end);
        const auto tags=read32(cursor,end);need(tags<=uint64_t(end-cursor)/8,"catalog way tag count");bool selected=false;std::set<std::string> keys;
        for(uint32_t t=0;t<tags;++t) {
            const auto key=read_string(cursor,end),value=read_string(cursor,end);
            need(keys.insert(key).second,"catalog duplicate tag key");
            selected|=(key=="natural" && value=="water")||(key=="waterway" && value=="riverbank")||(key=="landuse" && value=="reservoir");
        }
        const auto count=read32(cursor,end);
        need(count>=2 && count<=2000 && uint64_t(end-cursor)==uint64_t(count)*8 && catalog.refs.size()+count<=catalog.expected_refs,"catalog exact reference body/count");
        if(catalog.way_ids.empty()) {
            catalog.way_ids.reserve(catalog.expected_ways);catalog.offsets.reserve(catalog.expected_ways+1);
            catalog.water.reserve(catalog.expected_ways);catalog.refs.reserve(catalog.expected_refs);catalog.offsets.push_back(0);
        }
        for(uint32_t i=0;i<count;++i) {const auto node=read64(cursor,end);need(node>0 && node<(uint64_t(1)<<63),"catalog positive native reference");catalog.refs.push_back(node);}
        catalog.way_ids.push_back(identity);catalog.water.push_back(selected);catalog.tagged+=selected;catalog.offsets.push_back(catalog.refs.size());
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_catalog_ways_seal(Callback callback,void* user,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(catalog.points_sealed && !catalog.ways_sealed && catalog.way_ids.size()==catalog.expected_ways && catalog.refs.size()==catalog.expected_refs && callback,"catalog complete ways before seal");
        std::vector<uint8_t> raw;raw.reserve(16013);
        for(size_t rank=0;rank<catalog.way_ids.size();++rank) {
            raw.clear();put64(raw,catalog.way_ids[rank]);put32(raw,catalog.offsets[rank+1]-catalog.offsets[rank]);raw.push_back(catalog.water[rank]);
            for(auto i=catalog.offsets[rank];i<catalog.offsets[rank+1];++i)put64(raw,catalog.refs[i]);
            need(callback(user,50,raw.data(),raw.size())==0,"catalog every saved way field audit callback");
        }
        catalog.ways_sealed=true;
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_catalog_gather(
    const uint64_t* way_ids,const int8_t* directions,uint32_t members,Point* output,uint32_t capacity,uint32_t* written,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(catalog.ways_sealed && way_ids && directions && output && written && members>0 && members<=100000 && capacity<=2000000,"catalog gather arguments/state/caps");
        *written=0;uint64_t last=0;
        for(uint32_t m=0;m<members;++m) {
            need(directions[m]==1 || directions[m]==-1,"catalog member direction");const auto rank=way_rank(way_ids[m]);
            const auto begin=catalog.offsets[rank],end=catalog.offsets[rank+1];
            for(uint64_t step=0;step<end-begin;++step) {
                const auto identity=catalog.refs[directions[m]==1?begin+step:end-1-step];
                if(m && step==0) {need(identity==last,"catalog native-ID chain continuity");continue;}
                need(*written<capacity,"catalog object point capacity");output[(*written)++]=lookup(identity);last=identity;
            }
        }
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_catalog_stats(uint64_t* output,uint32_t count) noexcept {
    if(!output || count!=8)return -1;
    output[0]=catalog.points.size();output[1]=catalog.way_ids.size();output[2]=catalog.refs.size();output[3]=catalog.tagged;
    output[4]=catalog.points_sealed;output[5]=catalog.ways_sealed;
    output[6]=catalog.points.capacity()*sizeof(Point)+(catalog.way_ids.capacity()+catalog.offsets.capacity()+catalog.refs.capacity())*8+catalog.water.capacity();output[7]=catalog.failed;return 0;
}
