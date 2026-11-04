// Typed CSR/cost/reverse/turn encoding from closed cost facts. No source decoder.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <limits>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace {
constexpr uint32_t NONE = UINT32_MAX;
constexpr uint64_t OUTPUT_LIMIT = 192ull << 20;
void need(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
uint32_t u32(const uint8_t* p) { return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24; }
uint64_t u64(const uint8_t* p) { return u32(p) | uint64_t(u32(p+4)) << 32; }

struct File {
    FILE* stream = nullptr;
    explicit File(const std::string& name, bool output) {
        int fd = open(name.c_str(), output ? O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW : O_RDONLY | O_NOFOLLOW, 0600);
        need(fd >= 0, "Packed file open/freshness");
        struct stat state{};
        if (fstat(fd, &state) || !S_ISREG(state.st_mode) || state.st_nlink != 1 || (!output && state.st_size > 16777216)) {
            close(fd);throw std::runtime_error("Packed file type/link/size");
        }
        stream = fdopen(fd, output ? "wb" : "rb");
        if (!stream) { close(fd);throw std::runtime_error("Packed file stream"); }
        setvbuf(stream, nullptr, _IOFBF, 65536);
    }
    ~File() { if (stream) fclose(stream); }
    void finish() { need(fflush(stream) == 0, "Packed output flush");FILE* value=stream;stream=nullptr;need(fclose(value)==0, "Packed output close"); }
    File(const File&) = delete;
    File& operator=(const File&) = delete;
};

std::vector<std::string> paths(const std::string& root, const std::string& prefix) {
    std::vector<std::string> result;
    for (const auto& entry : std::filesystem::directory_iterator(root)) {
        auto name = entry.path().filename().string();
        if (name.size() != prefix.size()+9 || name.compare(0, prefix.size(), prefix) || name[prefix.size()] != '-' || name.substr(name.size()-4) != ".bin") continue;
        bool digits=true;for (size_t i=prefix.size()+1;i<prefix.size()+5;i++) digits &= name[i]>='0' && name[i]<='9';
        if (digits) result.push_back(entry.path().string());
    }
    std::sort(result.begin(),result.end());
    for (size_t i=0;i<result.size();i++) {
        char suffix[32];std::snprintf(suffix,sizeof suffix,"-%04zu.bin",i);
        need(std::filesystem::path(result[i]).filename() == prefix+suffix, "Packed contiguous fact chunks");
    }
    return result;
}

template<size_t WIDTH, class Callback>
uint64_t rows(const std::string& root, const std::string& prefix, uint64_t maximum, Callback consume) {
    uint64_t count=0;std::array<uint8_t,WIDTH> row{};
    for (const auto& name:paths(root,prefix)) {
        File input(name,false);
        while (auto bytes=std::fread(row.data(),1,WIDTH,input.stream)) {
            need(bytes==WIDTH && ++count<=maximum,"Packed input record size/count");consume(row.data(),count-1);
        }
        need(!std::ferror(input.stream),"Packed fact read");
    }
    return count;
}

struct Writer {
    std::string root;uint64_t total=0;
    explicit Writer(std::string value):root(std::move(value)) {}
    template<class Value> void write(const std::string& name, uint64_t count, unsigned width, Value value) {
        need(count<=16777216 && width>=1 && width<=4 && total+count*width<=OUTPUT_LIMIT,"Packed output limit");
        File output(root+"/"+name,true);uint8_t bytes[4];
        for (uint64_t i=0;i<count;i++) {
            uint32_t word=value(i);need(width==4 || word<(1u<<(8*width)),"Packed wire word range");
            for (unsigned j=0;j<width;j++) bytes[j]=word>>(8*j);
            need(std::fwrite(bytes,1,width,output.stream)==width,"Packed wire write");
        }
        output.finish();total+=count*width;
    }
};

struct Edge { uint32_t tail,head,way,original,mate,ticks; };
struct Rule { uint32_t from,via;uint64_t to;uint8_t kind; };
using Counts = std::array<uint64_t,12>;

Counts encode(const std::string& root, const std::string& output, const uint64_t* expected) {
    const uint64_t nodes=expected[0],vertices=expected[1],way_count=expected[2],pre_arcs=expected[3],post_arcs=expected[4],turn_count=expected[5];
    need(nodes>0 && nodes<=64000000 && vertices>0 && vertices<=0xffffff && way_count<=8000000 && pre_arcs<=0xffffff && post_arcs<=pre_arcs && turn_count<=2000000,"Packed declared dimensions");
    need(std::filesystem::is_directory(output),"Packed output directory");
    std::vector<uint32_t> anchors;anchors.reserve(vertices);
    rows<4>(root,"anchors",vertices,[&](const uint8_t* row,uint64_t) {
        uint32_t node=u32(row);need(node<nodes && (anchors.empty() || node>anchors.back()),"Packed anchor order/range");anchors.push_back(node);
    });need(anchors.size()==vertices,"Packed anchor count");
    std::vector<uint64_t> identities;identities.reserve(vertices);size_t cursor=0;uint64_t previous_id=0;
    auto seen=rows<8>(root,"ids",nodes,[&](const uint8_t* row,uint64_t ordinal) {
        uint64_t id=u64(row);need(id>previous_id,"Packed native ID order");previous_id=id;
        if (cursor<anchors.size() && ordinal==anchors[cursor]) { identities.push_back(id);cursor++; }
    });need(seen==nodes && cursor==vertices,"Packed selected/native anchor counts");
    std::vector<std::array<uint32_t,2>> xy;xy.reserve(vertices);cursor=0;
    seen=rows<8>(root,"xy",nodes,[&](const uint8_t* row,uint64_t ordinal) {
        int32_t x=int32_t(u32(row)),y=int32_t(u32(row+4));
        need(x>=-1800000000 && x<=1800000000 && y>=-900000000 && y<=900000000,"Packed coordinate domain");
        if (cursor<anchors.size() && ordinal==anchors[cursor]) { xy.push_back({uint32_t(x),uint32_t(y)});cursor++; }
    });need(seen==nodes && cursor==vertices,"Packed coordinate count");
    std::vector<uint8_t> flags;flags.reserve(vertices);
    rows<1>(root,"flags",vertices,[&](const uint8_t* row,uint64_t) { need(*row<8,"Packed node flag mask");flags.push_back(*row); });
    need(flags.size()==vertices,"Packed node flag count");
    std::vector<uint64_t> ways;ways.reserve(way_count);
    rows<32>(root,"ways",way_count,[&](const uint8_t* row,uint64_t) {
        auto id=u64(row);need(id>0 && (ways.empty() || id>ways.back()),"Packed way ID order");ways.push_back(id);
    });need(ways.size()==way_count,"Packed way count");
    std::vector<uint64_t> closed;
    rows<8>(root,"closures",2000000,[&](const uint8_t* row,uint64_t) {
        auto id=u64(row);need(id>0 && (closed.empty() || id>closed.back()),"Packed closure order");closed.push_back(id);
    });
    std::vector<Edge> edges;edges.reserve(post_arcs);
    std::array<uint32_t,3> prior_key{};int prior_direction=0;uint32_t prior_edge=NONE;
    seen=rows<32>(root,"arcs",pre_arcs,[&](const uint8_t* row,uint64_t) {
        uint32_t tail=u32(row),head=u32(row+4),way=u32(row+8),first=u32(row+12),last=u32(row+16);
        int direction=int8_t(row[20]);uint64_t ms=u64(row+24),ticks=(ms+124)/125;
        need(tail<vertices && head<vertices && way<way_count && first<last && (direction==1 || direction==-1) && !row[21] && !row[22] && !row[23] && ms>0 && ms<=uint64_t(UINT32_MAX)*125,"Packed arc fact range/padding/cost");
        std::array<uint32_t,3> key{way,first,last};
        need(prior_direction==0 || key>prior_key || (key==prior_key && prior_direction==1 && direction==-1),"Packed source arc ordering");
        bool eligible=!std::binary_search(closed.begin(),closed.end(),ways[way]);
        if (eligible) {
            need(edges.size()<post_arcs,"Packed retained arc bound");uint32_t index=edges.size();
            Edge edge{tail,head,way,index,NONE,uint32_t(ticks)};
            if (key==prior_key && prior_edge!=NONE) {
                auto& other=edges[prior_edge];need(other.tail==head && other.head==tail,"Packed physical reverse endpoints");other.mate=index;edge.mate=prior_edge;
            }
            edges.push_back(edge);prior_edge=index;
        } else prior_edge=NONE;
        prior_key=key;prior_direction=direction;
    });need(seen==pre_arcs && edges.size()==post_arcs,"Packed pre/post closure arc counts");
    std::sort(edges.begin(),edges.end(),[](const Edge& a,const Edge& b) { return std::tie(a.tail,a.original)<std::tie(b.tail,b.original); });
    std::vector<uint32_t> offsets(vertices+1,0),permutation(post_arcs);
    for (uint32_t i=0;i<edges.size();i++) { offsets[edges[i].tail+1]++;permutation[edges[i].original]=i; }
    for (size_t i=0;i<vertices;i++) offsets[i+1]+=offsets[i];
    for (auto& edge:edges) if (edge.mate!=NONE) edge.mate=permutation[edge.mate];
    std::vector<uint32_t>().swap(permutation);
    std::vector<Rule> rules;rules.reserve(turn_count);
    seen=rows<40>(root,"turns",turn_count,[&](const uint8_t* row,uint64_t) {
        uint64_t from=u64(row+8),via=u64(row+16),to=u64(row+24);uint8_t kind=row[32];
        need(kind<10 && std::all_of(row+33,row+40,[](uint8_t x){return !x;}),"Packed source turn kind/padding");
        auto a=std::lower_bound(ways.begin(),ways.end(),from),b=std::lower_bound(identities.begin(),identities.end(),via);
        if (a!=ways.end() && *a==from && b!=identities.end() && *b==via) rules.push_back({uint32_t(a-ways.begin()),uint32_t(b-identities.begin()),to,kind});
    });need(seen==turn_count,"Packed source turn count");
    std::sort(rules.begin(),rules.end(),[](const Rule& a,const Rule& b) { return std::tie(a.from,a.via)<std::tie(b.from,b.via); });
    std::vector<uint32_t> forbidden,cost_keys,cost_values,reverse_keys,reverse_values;std::vector<uint8_t> reverse;reverse.reserve(post_arcs);
    uint64_t maximum_degree=0;
    for (size_t i=0;i<vertices;i++) maximum_degree=std::max(maximum_degree,uint64_t(offsets[i+1]-offsets[i]));
    for (uint32_t i=0;i<edges.size();i++) {
        const auto& edge=edges[i];
        if (edge.ticks>=65535) { cost_keys.push_back(i);cost_values.push_back(edge.ticks);need(cost_keys.size()*7<=2097152,"Packed cost overflow budget"); }
        if (edge.mate==NONE) reverse.push_back(255);
        else {
            uint32_t other=edge.mate;need(other<edges.size() && edges[other].mate==i && edges[other].tail==edge.head && edges[other].head==edge.tail,"Packed symmetric physical reverse");
            uint32_t ordinal=other-offsets[edge.head];need(ordinal<offsets[edge.head+1]-offsets[edge.head],"Packed reverse row");
            reverse.push_back(std::min(ordinal,254u));
            if (ordinal>=254) { reverse_keys.push_back(i);reverse_values.push_back(other);need(reverse_keys.size()*6<=524288,"Packed reverse overflow budget"); }
        }
        const auto key=std::make_pair(edge.way,edge.head);
        auto first=std::lower_bound(rules.begin(),rules.end(),key,[](const Rule& rule,const auto& value){return std::make_pair(rule.from,rule.via)<value;});
        if (first==rules.end() || first->from!=edge.way || first->via!=edge.head) continue;
        auto last=first;while (last!=rules.end() && last->from==edge.way && last->via==edge.head) ++last;
        for (uint32_t next=offsets[edge.head];next<offsets[edge.head+1];next++) {
            bool has_only=false,only_match=false,no_match=false;
            for (auto rule=first;rule!=last;rule++) {
                bool match=ways[edges[next].way]==rule->to;
                if (ways[edge.way]==rule->to) match &= (rule->kind==3 || rule->kind==9) ? next==edge.mate : next!=edge.mate;
                if (rule->kind>=6) { has_only=true;only_match |= match; } else no_match |= match;
            }
            if (no_match || (has_only && !only_match)) {
                forbidden.push_back(i);forbidden.push_back(next);need(forbidden.size()*3<=6291456,"Packed forbidden pair budget");
            }
        }
    }
    Writer writer(output);
    writer.write("xy.i32",2*vertices,4,[&](size_t i){return xy[i/2][i%2];});
    writer.write("offsets.u24",vertices+1,3,[&](size_t i){return offsets[i];});
    writer.write("targets.u24",post_arcs,3,[&](size_t i){return edges[i].head;});
    writer.write("costs.u16",post_arcs,2,[&](size_t i){return std::min(edges[i].ticks,65535u);});
    writer.write("cost-overflow-arcs.u24",cost_keys.size(),3,[&](size_t i){return cost_keys[i];});
    writer.write("cost-overflow-ticks.u32",cost_values.size(),4,[&](size_t i){return cost_values[i];});
    writer.write("reverse.u8",post_arcs,1,[&](size_t i){return reverse[i];});
    writer.write("reverse-overflow-arcs.u24",reverse_keys.size(),3,[&](size_t i){return reverse_keys[i];});
    writer.write("reverse-overflow-targets.u24",reverse_values.size(),3,[&](size_t i){return reverse_values[i];});
    writer.write("node-flags.u8",vertices,1,[&](size_t i){return flags[i];});
    writer.write("forbidden-turns.u24",forbidden.size(),3,[&](size_t i){return forbidden[i];});
    return {nodes,vertices,way_count,pre_arcs,post_arcs,turn_count,cost_keys.size(),reverse_keys.size(),forbidden.size()/2,writer.total,maximum_degree,rules.size()};
}
}

extern "C" __attribute__((visibility("default"))) uint32_t gp_car_packed_abi() { return 0x10000; }
extern "C" __attribute__((visibility("default"))) int gp_car_packed_encode(const char* source,const char* output,const uint64_t* expected,uint64_t* result,char* error,size_t capacity) {
    try {
        need(source && output && expected && result,"Packed required pointers");auto counts=encode(source,output,expected);std::copy(counts.begin(),counts.end(),result);return 0;
    } catch (const std::exception& exception) {
        if (error && capacity) std::snprintf(error,capacity,"%s",exception.what());return 1;
    }
}
