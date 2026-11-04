// New metadata resolution/turn augmentation over immutable pre-closure facts.
// Reuse the qualified fixed-width reader/formatter; never decode source PBF.
#include "coarse_osm_car_packed_native_v1.cpp"

namespace entry_metadata {
constexpr uint64_t max_rules=100000, max_ids=200000, max_pairs=2000000;
struct Ends { uint32_t tail,head; };
struct Candidate { uint64_t id,from,via,to; };
class Input {
public:
    FILE* stream=nullptr;
    explicit Input(const std::string& path) {
        int fd=::open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);need(fd>=0,"Entry input open");
        struct stat state{};
        if(::fstat(fd,&state) || !S_ISREG(state.st_mode) || state.st_nlink!=1 || state.st_size<0 || state.st_size>67108864) {::close(fd);throw std::runtime_error("Entry input type/link/size");}
        stream=::fdopen(fd,"rb");if(!stream){::close(fd);throw std::runtime_error("Entry input stream");}
        ::setvbuf(stream,nullptr,_IOFBF,65536);
    }
    ~Input(){if(stream)::fclose(stream);}
    Input(const Input&)=delete;Input& operator=(const Input&)=delete;
};

template<size_t WIDTH,class Callback>
uint64_t fixed(const std::string& path,uint64_t maximum,Callback consume) {
    Input file(path);std::array<uint8_t,WIDTH> row{};uint64_t count=0;
    while(auto n=std::fread(row.data(),1,WIDTH,file.stream)) {
        need(n==WIDTH && count<maximum,"Entry fixed record size/count");consume(row.data(),count++);
    }
    need(!std::ferror(file.stream),"Entry fixed input read");return count;
}
std::vector<uint64_t> identities(const std::string& path) {
    std::vector<uint64_t> result;
    fixed<8>(path,max_ids,[&](const uint8_t* p,uint64_t){auto id=u64(p);need(id && id<=INT64_MAX && (result.empty() || result.back()<id),"Entry sorted native IDs");result.push_back(id);});
    return result;
}
void word(FILE* stream,uint64_t value,unsigned width) {
    uint8_t raw[8];for(unsigned i=0;i<width;i++)raw[i]=value>>(8*i);
    need(std::fwrite(raw,1,width,stream)==width,"Entry output write");
}
void write_ids(const std::string& path,const std::vector<uint64_t>& ids) {
    File file(path,true);for(auto id:ids)word(file.stream,id,8);file.finish();
}
uint32_t ordinal(const std::vector<uint64_t>& ways,uint64_t id) {
    auto at=std::lower_bound(ways.begin(),ways.end(),id);return at!=ways.end() && *at==id?uint32_t(at-ways.begin()):NONE;
}
std::vector<uint64_t> way_ids(const std::string& root,uint64_t count) {
    need(count && count<=8000000,"Entry way count bound");std::vector<uint64_t> ways;ways.reserve(count);
    auto seen=rows<32>(root,"ways",count,[&](const uint8_t* p,uint64_t){auto id=u64(p);need(id && id<=INT64_MAX && (ways.empty() || ways.back()<id),"Entry source way order");ways.push_back(id);});
    need(seen==count,"Entry source way count");return ways;
}
std::vector<uint64_t> old_closures(const std::string& root) {
    std::vector<uint64_t> ids;
    rows<8>(root,"closures",max_ids,[&](const uint8_t* p,uint64_t){auto id=u64(p);need(id && id<=INT64_MAX && (ids.empty() || ids.back()<id),"Entry original closure order");ids.push_back(id);});
    return ids;
}

void resolve(const std::string& source,const std::string& rules_path,const std::string& fallback_path,const std::string& output,const uint64_t* dims,uint64_t* result) {
    const auto ways_count=dims[0],vertices=dims[1],pre=dims[2],rules_count=dims[3],fallback_count=dims[4];
    need(vertices && vertices<=0xffffff && pre<=0xffffff && rules_count<=max_rules && fallback_count<=max_ids,"Entry declared dimensions");
    auto ways=way_ids(source,ways_count);auto old=old_closures(source);auto closed=identities(fallback_path);
    need(closed.size()==fallback_count && std::includes(old.begin(),old.end(),closed.begin(),closed.end()),"Entry fallback subset/count");
    std::vector<uint32_t> offsets(ways_count+1);std::vector<Ends> ends;ends.reserve(pre);uint32_t cursor=0;
    auto seen=rows<32>(source,"arcs",pre,[&](const uint8_t* p,uint64_t i){
        auto a=u32(p),b=u32(p+4),way=u32(p+8);int direction=int8_t(p[20]);
        need(a<vertices && b<vertices && way<ways_count && (ends.empty() || way+1>=cursor) && u32(p+12)<u32(p+16) && (direction==1 || direction==-1) && !p[21] && !p[22] && !p[23],"Entry source arc domain/order");
        while(cursor<=way)offsets[cursor++]=i;ends.push_back({a,b});
    });
    need(seen==pre,"Entry complete pre-arc count");while(cursor<=ways_count)offsets[cursor++]=pre;
    std::vector<std::pair<uint32_t,uint32_t>> pairs;std::vector<std::array<uint64_t,3>> decisions;
    uint64_t prior=0,resolved=0,missing=0,no_join=0;
    auto add_fallback=[&](const Candidate& c){closed.push_back(c.from);closed.push_back(c.via);closed.push_back(c.to);};
    seen=fixed<32>(rules_path,max_rules,[&](const uint8_t* p,uint64_t){
        Candidate c{u64(p),u64(p+8),u64(p+16),u64(p+24)};
        need(c.id>prior && c.id<=INT64_MAX && c.from && c.via && c.to && c.from<=INT64_MAX && c.via<=INT64_MAX && c.to<=INT64_MAX && c.from!=c.via && c.to!=c.via,"Entry candidate identity/shape");prior=c.id;
        for(auto id:{c.from,c.via,c.to})need(std::binary_search(old.begin(),old.end(),id),"Entry candidate absent from original closures");
        const auto a=ordinal(ways,c.from),b=ordinal(ways,c.via),d=ordinal(ways,c.to);
        if(a==NONE || b==NONE || d==NONE || offsets[a]==offsets[a+1] || offsets[b]==offsets[b+1] || offsets[d]==offsets[d+1]) {
            add_fallback(c);missing++;decisions.push_back({c.id,1,0});return;
        }
        need(uint64_t(offsets[a+1]-offsets[a])+offsets[b+1]-offsets[b]<=200000,"Entry per-rule arc bound");
        std::vector<std::pair<uint32_t,uint32_t>> heads,tails;
        for(auto i=offsets[a];i<offsets[a+1];i++)heads.push_back({ends[i].head,i});
        for(auto i=offsets[b];i<offsets[b+1];i++)tails.push_back({ends[i].tail,i});
        std::sort(heads.begin(),heads.end());std::sort(tails.begin(),tails.end());
        size_t i=0,j=0,before=pairs.size();
        while(i<heads.size() && j<tails.size()) {
            if(heads[i].first<tails[j].first){i++;continue;}if(tails[j].first<heads[i].first){j++;continue;}
            size_t ie=i+1,je=j+1;while(ie<heads.size() && heads[ie].first==heads[i].first)ie++;while(je<tails.size() && tails[je].first==tails[j].first)je++;
            for(size_t x=i;x<ie;x++)for(size_t y=j;y<je;y++){need(pairs.size()<max_pairs,"Entry pre-pair cap");pairs.push_back({heads[x].second,tails[y].second});}
            i=ie;j=je;
        }
        if(before==pairs.size()){add_fallback(c);no_join++;decisions.push_back({c.id,2,0});}
        else {resolved++;decisions.push_back({c.id,0,pairs.size()-before});}
    });
    need(seen==rules_count,"Entry complete candidate count");std::sort(closed.begin(),closed.end());closed.erase(std::unique(closed.begin(),closed.end()),closed.end());
    need(closed.size()<=max_ids && std::includes(old.begin(),old.end(),closed.begin(),closed.end()),"Entry final closure subset");
    uint64_t post=pre;for(auto id:closed){auto way=ordinal(ways,id);if(way!=NONE)post-=offsets[way+1]-offsets[way];}
    std::sort(pairs.begin(),pairs.end());pairs.erase(std::unique(pairs.begin(),pairs.end()),pairs.end());
    write_ids(output+"/closures-0000.bin",closed);
    {File file(output+"/entry-pairs-pre.u32",true);for(auto pair:pairs){need(ends[pair.first].head==ends[pair.second].tail,"Entry native shared node proof");word(file.stream,pair.first,4);word(file.stream,pair.second,4);}file.finish();}
    {File file(output+"/decisions.bin",true);for(auto row:decisions){word(file.stream,row[0],8);word(file.stream,row[1],4);word(file.stream,row[2],4);}file.finish();}
    std::array<uint64_t,9> counts{rules_count,resolved,missing,no_join,old.size(),closed.size(),pairs.size(),pre,post};std::copy(counts.begin(),counts.end(),result);
}

std::vector<uint32_t> words24(const std::string& path,uint64_t maximum) {
    std::vector<uint32_t> out;fixed<3>(path,maximum,[&](const uint8_t* p,uint64_t){out.push_back(uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16);});return out;
}
void augment(const std::string& source,const std::string& closed_path,const std::string& pairs_path,const std::string& routing,const std::string& output,const uint64_t* dims,uint64_t* result) {
    const auto ways_count=dims[0],vertices=dims[1],pre=dims[2],post=dims[3];
    need(vertices && vertices<=0xffffff && pre<=0xffffff && post<=pre,"Entry augmentation dimensions");
    auto ways=way_ids(source,ways_count),old=old_closures(source),closed=identities(closed_path);
    need(std::includes(old.begin(),old.end(),closed.begin(),closed.end()),"Entry augmentation closure subset");
    auto offsets=words24(routing+"/offsets.u24",vertices+1),targets=words24(routing+"/targets.u24",post);
    need(offsets.size()==vertices+1 && offsets.front()==0 && offsets.back()==post && targets.size()==post && std::is_sorted(offsets.begin(),offsets.end()),"Entry CSR dimensions/order");
    std::vector<uint32_t> cursor(offsets.begin(),offsets.end()-1),mapping(pre,NONE);std::vector<uint8_t> old_blocked(pre);uint64_t retained=0;
    auto seen=rows<32>(source,"arcs",pre,[&](const uint8_t* p,uint64_t i){
        auto tail=u32(p),head=u32(p+4),way=u32(p+8);need(tail<vertices && head<vertices && way<ways_count,"Entry mapping arc domain");
        old_blocked[i]=std::binary_search(old.begin(),old.end(),ways[way]);
        if(std::binary_search(closed.begin(),closed.end(),ways[way]))return;
        auto csr=cursor[tail]++;need(csr<offsets[tail+1] && targets[csr]==head,"Entry actual source-to-CSR correspondence");mapping[i]=csr;retained++;
    });
    need(seen==pre && retained==post,"Entry complete mapping count");for(size_t i=0;i<vertices;i++)need(cursor[i]==offsets[i+1],"Entry complete CSR rows");
    auto raw=words24(routing+"/forbidden-turns.u24",2097152);need(raw.size()%2==0,"Entry original pair shape");
    std::vector<std::pair<uint32_t,uint32_t>> pairs;for(size_t i=0;i<raw.size();i+=2){need(raw[i]<post && raw[i+1]<post,"Entry original pair domain");pairs.push_back({raw[i],raw[i+1]});}
    need(std::is_sorted(pairs.begin(),pairs.end()) && std::adjacent_find(pairs.begin(),pairs.end())==pairs.end(),"Entry original pair order/unique");
    uint64_t original=pairs.size(),active=0,dropped=0;std::pair<uint32_t,uint32_t> prior{};bool has_prior=false;
    auto pre_pairs=fixed<8>(pairs_path,max_pairs,[&](const uint8_t* p,uint64_t){
        auto a=u32(p),b=u32(p+4);std::pair<uint32_t,uint32_t> key{a,b};
        need(a<pre && b<pre && (!has_prior || prior<key) && old_blocked[a] && old_blocked[b],"Entry pre-pair order/domain/baseline safety");prior=key;has_prior=true;
        if(mapping[a]==NONE || mapping[b]==NONE){dropped++;return;}
        auto from=mapping[a],to=mapping[b];auto row=std::upper_bound(offsets.begin(),offsets.end(),to)-offsets.begin()-1;
        need(row<vertices && targets[from]==row,"Entry actual CSR shared node");pairs.push_back({from,to});active++;
    });
    std::sort(pairs.begin(),pairs.end());pairs.erase(std::unique(pairs.begin(),pairs.end()),pairs.end());need(pairs.size()*6<=6291456,"Entry final forbidden pair budget");
    {File file(output,true);for(auto pair:pairs){word(file.stream,pair.first,3);word(file.stream,pair.second,3);}file.finish();}
    std::array<uint64_t,6> counts{pre_pairs,original,active,dropped,pairs.size(),retained};std::copy(counts.begin(),counts.end(),result);
}
}

extern "C" __attribute__((visibility("default"))) uint32_t gp_car_entry_abi(){return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_car_entry_resolve(const char* source,const char* rules,const char* fallback,const char* output,const uint64_t* dims,uint64_t* counts,char* error,size_t size) {
    try {need(source && rules && fallback && output && dims && counts,"Entry resolver pointers");entry_metadata::resolve(source,rules,fallback,output,dims,counts);return 0;}
    catch(const std::exception& e){if(error && size)std::snprintf(error,size,"%s",e.what());return 1;}
}
extern "C" __attribute__((visibility("default"))) int gp_car_entry_augment(const char* source,const char* closed,const char* pairs,const char* routing,const char* output,const uint64_t* dims,uint64_t* counts,char* error,size_t size) {
    try {need(source && closed && pairs && routing && output && dims && counts,"Entry augmentation pointers");entry_metadata::augment(source,closed,pairs,routing,output,dims,counts);return 0;}
    catch(const std::exception& e){if(error && size)std::snprintf(error,size,"%s",e.what());return 1;}
}
