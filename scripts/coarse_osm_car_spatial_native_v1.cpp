// Lossless spatial permutation of an already audited packed graph.
// Reuse the frozen bounded writer; the source-fact encoder is never invoked.
#include "coarse_osm_car_packed_native_v1.cpp"

namespace {
std::vector<uint8_t> packed_bytes(const std::string& path) {
    int fd=open(path.c_str(),O_RDONLY|O_NOFOLLOW);need(fd>=0,"Spatial input open");
    struct stat state{};
    if (fstat(fd,&state) || !S_ISREG(state.st_mode) || state.st_nlink!=1 || state.st_size<0 || state.st_size>67108864) {
        close(fd);throw std::runtime_error("Spatial input type/link/size");
    }
    std::vector<uint8_t> bytes(state.st_size);size_t cursor=0;
    while (cursor<bytes.size()) { ssize_t amount=read(fd,bytes.data()+cursor,bytes.size()-cursor);if (amount<=0) {close(fd);throw std::runtime_error("Spatial input short read");}cursor+=amount; }
    need(close(fd)==0,"Spatial input close");return bytes;
}

std::vector<uint32_t> packed_words(const std::string& path,unsigned width) {
    auto bytes=packed_bytes(path);need(bytes.size()%width==0,"Spatial input word shape");
    std::vector<uint32_t> values;values.reserve(bytes.size()/width);
    for (size_t i=0;i<bytes.size();i+=width) {
        uint32_t word=0;for (unsigned j=0;j<width;j++) word|=uint32_t(bytes[i+j])<<(8*j);values.push_back(word);
    }
    return values;
}

uint64_t spread(uint32_t value) {
    uint64_t word=value;
    word=(word|(word<<16))&0x0000ffff0000ffffull;
    word=(word|(word<<8))&0x00ff00ff00ff00ffull;
    word=(word|(word<<4))&0x0f0f0f0f0f0f0f0full;
    word=(word|(word<<2))&0x3333333333333333ull;
    return (word|(word<<1))&0x5555555555555555ull;
}

uint64_t spatial_key(int32_t x,int32_t y) {
    need(x>=-1800000000 && x<=1800000000 && y>=-900000000 && y<=900000000,"Spatial coordinate range");
    return spread(uint32_t(int64_t(x)+1800000000)) | spread(uint32_t(int64_t(y)+900000000))<<1;
}

struct Position { uint64_t key;uint32_t old; };
struct Overflow { uint32_t key,value; };

std::array<uint64_t,7> spatial(const std::string& input,const std::string& output) {
    auto offsets=packed_words(input+"/offsets.u24",3),targets=packed_words(input+"/targets.u24",3),xy=packed_words(input+"/xy.i32",4);
    auto flags=packed_bytes(input+"/node-flags.u8"),reverse=packed_bytes(input+"/reverse.u8");
    auto costs=packed_words(input+"/costs.u16",2),cost_keys=packed_words(input+"/cost-overflow-arcs.u24",3),cost_values=packed_words(input+"/cost-overflow-ticks.u32",4);
    auto reverse_keys=packed_words(input+"/reverse-overflow-arcs.u24",3),reverse_values=packed_words(input+"/reverse-overflow-targets.u24",3),turns=packed_words(input+"/forbidden-turns.u24",3);
    uint32_t vertices=flags.size(),arcs=targets.size();
    need(vertices>0 && vertices<=0xffffff && arcs<=0xffffff && xy.size()==2ull*vertices && offsets.size()==vertices+1ull && offsets[0]==0 && offsets.back()==arcs,"Spatial vertex shape");
    need(reverse.size()==arcs && costs.size()==arcs && turns.size()%2==0 && cost_keys.size()==cost_values.size() && reverse_keys.size()==reverse_values.size(),"Spatial arc shape");
    auto valid_keys=[&](const std::vector<uint32_t>& keys) {
        for (size_t i=0;i<keys.size();i++) need(keys[i]<arcs && (!i || keys[i]>keys[i-1]),"Spatial overflow key order/range");
    };valid_keys(cost_keys);valid_keys(reverse_keys);
    size_t cost_cursor=0,reverse_cursor=0;
    for (uint32_t i=0;i<arcs;i++) {
        need(targets[i]<vertices && costs[i]>0,"Spatial arc target/cost range");
        if (costs[i]==65535) {need(cost_cursor<cost_keys.size() && cost_keys[cost_cursor]==i && cost_values[cost_cursor]>=65535,"Spatial cost overflow coverage");cost_cursor++;}
        if (reverse[i]==254) {need(reverse_cursor<reverse_keys.size() && reverse_keys[reverse_cursor]==i && reverse_values[reverse_cursor]<arcs,"Spatial reverse overflow coverage");reverse_cursor++;}
    }
    need(cost_cursor==cost_keys.size() && reverse_cursor==reverse_keys.size(),"Spatial exact overflow roster");
    std::vector<Position> order;order.reserve(vertices);
    for (uint32_t old=0;old<vertices;old++) {
        need(offsets[old]<=offsets[old+1] && offsets[old+1]<=arcs && flags[old]<8,"Spatial CSR/flags");
        order.push_back({spatial_key(int32_t(xy[2ull*old]),int32_t(xy[2ull*old+1])),old});
    }
    std::sort(order.begin(),order.end(),[](const Position& a,const Position& b){return std::tie(a.key,a.old)<std::tie(b.key,b.old);});
    std::vector<uint32_t> vertex_map(vertices),arc_map(arcs),new_offsets(vertices+1,0),cell_keys,cell_offsets;
    for (uint32_t i=0;i<vertices;i++) {
        uint32_t old=order[i].old;vertex_map[old]=i;new_offsets[i+1]=new_offsets[i]+offsets[old+1]-offsets[old];
        uint32_t cell=order[i].key>>40;
        if (cell_keys.empty() || cell!=cell_keys.back()) {cell_keys.push_back(cell);cell_offsets.push_back(i);}
        for (uint32_t arc=offsets[old];arc<offsets[old+1];arc++) arc_map[arc]=new_offsets[i]+arc-offsets[old];
    }
    cell_offsets.push_back(vertices);
    need(cell_keys.size()*6+3<=1048576,"Spatial anchor index budget");
    std::vector<uint32_t> old_arcs;old_arcs.reserve(arcs);
    for (const auto& point:order) for (uint32_t arc=offsets[point.old];arc<offsets[point.old+1];arc++) old_arcs.push_back(arc);
    auto permute_overflow=[&](const std::vector<uint32_t>& keys,const std::vector<uint32_t>& values,bool arc_values) {
        std::vector<Overflow> result;result.reserve(keys.size());
        for (size_t i=0;i<keys.size();i++) result.push_back({arc_map[keys[i]],arc_values?arc_map[values[i]]:values[i]});
        std::sort(result.begin(),result.end(),[](const Overflow& a,const Overflow& b){return a.key<b.key;});return result;
    };
    auto new_cost=permute_overflow(cost_keys,cost_values,false),new_reverse=permute_overflow(reverse_keys,reverse_values,true);
    std::vector<uint64_t> new_turns;new_turns.reserve(turns.size()/2);
    uint64_t previous=0;
    for (size_t i=0;i<turns.size();i+=2) {
        uint32_t a=turns[i],b=turns[i+1];need(a<arcs && b<arcs,"Spatial source turn range");
        uint64_t key=uint64_t(a)<<24|b;need(i==0 || key>previous,"Spatial source turn order");previous=key;
        new_turns.push_back(uint64_t(arc_map[a])<<24|arc_map[b]);
    }
    std::sort(new_turns.begin(),new_turns.end());
    Writer writer(output);
    writer.write("xy.i32",2ull*vertices,4,[&](size_t i){return xy[2ull*order[i/2].old+i%2];});
    writer.write("offsets.u24",vertices+1ull,3,[&](size_t i){return new_offsets[i];});
    writer.write("targets.u24",arcs,3,[&](size_t i){return vertex_map[targets[old_arcs[i]]];});
    writer.write("costs.u16",arcs,2,[&](size_t i){return costs[old_arcs[i]];});
    writer.write("cost-overflow-arcs.u24",new_cost.size(),3,[&](size_t i){return new_cost[i].key;});
    writer.write("cost-overflow-ticks.u32",new_cost.size(),4,[&](size_t i){return new_cost[i].value;});
    writer.write("reverse.u8",arcs,1,[&](size_t i){return reverse[old_arcs[i]];});
    writer.write("reverse-overflow-arcs.u24",new_reverse.size(),3,[&](size_t i){return new_reverse[i].key;});
    writer.write("reverse-overflow-targets.u24",new_reverse.size(),3,[&](size_t i){return new_reverse[i].value;});
    writer.write("node-flags.u8",vertices,1,[&](size_t i){return flags[order[i].old];});
    writer.write("forbidden-turns.u24",2*new_turns.size(),3,[&](size_t i){return uint32_t(i%2 ? new_turns[i/2]&0xffffff : new_turns[i/2]>>24);});
    uint64_t routing_bytes=writer.total;
    writer.write("cell-keys.u24",cell_keys.size(),3,[&](size_t i){return cell_keys[i];});
    writer.write("cell-offsets.u24",cell_offsets.size(),3,[&](size_t i){return cell_offsets[i];});
    uint64_t spatial_bytes=writer.total-routing_bytes;
    writer.write("new-vertex-to-old.u32",vertices,4,[&](size_t i){return order[i].old;});
    writer.write("old-arc-to-new.u32",arcs,4,[&](size_t i){return arc_map[i];});
    return {vertices,arcs,routing_bytes,cell_keys.size(),spatial_bytes,writer.total,new_turns.size()};
}
}

extern "C" __attribute__((visibility("default"))) uint32_t gp_car_spatial_abi() { return 0x10000; }
extern "C" __attribute__((visibility("default"))) int gp_car_spatial_encode(const char* input,const char* output,uint64_t* result,char* error,size_t capacity) {
    try {need(input && output && result,"Spatial required pointers");auto counts=spatial(input,output);std::copy(counts.begin(),counts.end(),result);return 0;}
    catch (const std::exception& exception) {if (error && capacity) std::snprintf(error,capacity,"%s",exception.what());return 1;}
}
