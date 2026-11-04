// Fixed-record external-sort/count kernel. No graph, coordinates or source objects.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <memory>
#include <queue>
#include <stdexcept>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <vector>

namespace {
struct Failure { const char* message; };
void need(bool ok,const char* message){if(!ok)throw Failure{message};}
std::uint64_t add(std::uint64_t a,std::uint64_t b){need(b<=UINT64_MAX-a,"counter_overflow");return a+b;}
struct Ref { std::uint64_t node,way;std::uint32_t degree,flags; };
static_assert(sizeof(Ref)==24,"reference record width");
bool less(const Ref& a,const Ref& b){
    if(a.node!=b.node)return a.node<b.node;
    if(a.way!=b.way)return a.way<b.way;
    if(a.flags!=b.flags)return a.flags<b.flags;
    return a.degree<b.degree;
}
void valid_id(std::uint64_t id){need(id>0 && id<=INT64_MAX,"positive_signed63_id");}
void valid(const Ref& r){valid_id(r.node);valid_id(r.way);need(r.flags<=1 && r.degree==(r.flags?1:2),"reference_degree_endpoint_flag");}
void environment(){const std::uint16_t one=1;need(*reinterpret_cast<const unsigned char*>(&one)==1,"little_endian_required");}
void error_text(char* out,std::uint32_t size,const char* text){if(out && size){const auto n=std::min<std::size_t>(size-1,std::strlen(text));std::memcpy(out,text,n);out[n]=0;}}
template<class Action> int guarded(Action action,char* error,std::uint32_t size) noexcept {
    if(!error || !size || size>1024)return -1;error[0]=0;
    try{environment();action();return 0;}catch(const Failure& f){error_text(error,size,f.message);}
    catch(...){error_text(error,size,"kernel_io_or_allocation_failure");}return -2;
}
class Reader {
    std::FILE* file_=nullptr;struct stat before_{};std::uint64_t bytes_=0;bool ended_=false;
public:
    Reader(const char* path,std::size_t width){
        need(path && strnlen(path,4097)<=4096,"path_bound");
        const int fd=::open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);need(fd>=0,"input_open");
        if(::fstat(fd,&before_)!=0 || !S_ISREG(before_.st_mode) || before_.st_size<0 || before_.st_size>67108864 || static_cast<std::uint64_t>(before_.st_size)%width){::close(fd);throw Failure{"input_type_size"};}
        file_=::fdopen(fd,"rb");if(!file_){::close(fd);throw Failure{"input_stream"};}
    }
    ~Reader(){if(file_)std::fclose(file_);}
    bool next(void* row,std::size_t width){
        need(!ended_,"read_after_eof");const auto n=std::fread(row,1,width,file_);bytes_=add(bytes_,n);
        if(!n){
            need(!std::ferror(file_) && bytes_==static_cast<std::uint64_t>(before_.st_size),"input_eof_length");
            struct stat after{};need(::fstat(::fileno(file_),&after)==0 && before_.st_size==after.st_size && before_.st_mtime==after.st_mtime && before_.st_ctime==after.st_ctime,"input_stat_drift");
            ended_=true;return false;
        }
        need(n==width,"truncated_record");return true;
    }
};
struct TagStream {
    const char* const* paths;std::uint32_t count,index=0;std::unique_ptr<Reader> reader;
    std::uint64_t current=0,previous=0,rows=0,limit=0;bool available=false;
    TagStream(const char* const* p,std::uint32_t n,std::uint64_t cap):paths(p),count(n),limit(cap){advance();}
    void advance(){
        while(index<count){
            if(!reader)reader=std::make_unique<Reader>(paths[index],8);
            if(reader->next(&current,8)){valid_id(current);need(current>previous,"tag_id_order");previous=current;rows=add(rows,1);need(rows<=limit,"tag_row_cap");available=true;return;}
            reader.reset();++index;
        }
        available=false;
    }
    bool has(std::uint64_t id){while(available && current<id)advance();return available && current==id;}
    void finish(){while(available)advance();need(rows==limit,"tag_total_count");}
};
void sorted_ids(const std::uint64_t* ids,std::uint64_t n){
    need(!n || ids,"null_metadata_ids");for(std::uint64_t k=0;k<n;++k){valid_id(ids[k]);need(!k || ids[k-1]<=ids[k],"metadata_id_order");}
}
bool has(const std::uint64_t* ids,std::uint64_t n,std::uint64_t id){return n && std::binary_search(ids,ids+n,id);}
struct Item { Ref row;std::uint32_t part; };
struct Later { bool operator()(const Item& a,const Item& b) const {return less(b.row,a.row) || (!less(a.row,b.row) && a.part>b.part);} };
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_topology_abi() noexcept {return 0x10000;}
extern "C" __attribute__((visibility("default")))
int gp_topology_sort_refs(void* data,std::uint64_t n,char* error,std::uint32_t size) noexcept {
    return guarded([&]{need(n<=2000000 && (!n || data) && reinterpret_cast<std::uintptr_t>(data)%alignof(Ref)==0,"sort_reference_buffer_bound");auto* rows=static_cast<Ref*>(data);
        for(std::uint64_t k=0;k<n;++k)valid(rows[k]);if(n)std::sort(rows,rows+n,less);},error,size);
}
extern "C" __attribute__((visibility("default")))
int gp_topology_sort_ids(void* data,std::uint64_t n,char* error,std::uint32_t size) noexcept {
    return guarded([&]{need(n<=67108864 && (!n || data) && reinterpret_cast<std::uintptr_t>(data)%8==0,"sort_id_buffer_bound");auto* ids=static_cast<std::uint64_t*>(data);
        for(std::uint64_t k=0;k<n;++k)valid_id(ids[k]);if(n)std::sort(ids,ids+n);},error,size);
}
extern "C" __attribute__((visibility("default")))
int gp_topology_count_files(const char* const* ref_paths,std::uint32_t ref_parts,const char* const* tag_paths,std::uint32_t tag_parts,
    const std::uint64_t* relation_nodes,std::uint64_t node_count,const std::uint64_t* relation_ways,std::uint64_t way_count,
    std::uint64_t expected_refs,std::uint64_t expected_ways,std::uint64_t expected_tags,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept {
    if(!receipt || receipt_count!=18)return -1;std::fill(receipt,receipt+18,0);
    return guarded([&]{
        need(ref_parts<=256 && tag_parts<=256 && (!ref_parts || ref_paths) && (!tag_parts || tag_paths),"input_part_cap");
        need(node_count<=67108864 && way_count<=67108864-node_count && expected_refs<=509547029 && expected_ways<=expected_refs/2,"aggregate_row_cap");
        sorted_ids(relation_nodes,node_count);sorted_ids(relation_ways,way_count);
        need(expected_tags<=1606229364,"tag_aggregate_cap");TagStream tags(tag_paths,tag_parts,expected_tags);std::vector<std::unique_ptr<Reader>> readers;std::vector<Ref> previous(ref_parts);std::vector<bool> seen(ref_parts,false);
        std::priority_queue<Item,std::vector<Item>,Later> queue;
        const auto advance=[&](std::uint32_t part){Ref row{};if(readers[part]->next(&row,sizeof(row))){valid(row);need(!seen[part] || !less(row,previous[part]),"reference_part_order");previous[part]=row;seen[part]=true;queue.push({row,part});}};
        for(std::uint32_t k=0;k<ref_parts;++k){readers.push_back(std::make_unique<Reader>(ref_paths[k],24));advance(k);}
        std::uint64_t id=0,degree=0,internal=0;bool endpoint=false,relation_way=false;
        const auto finish=[&]{if(!id)return;const bool tagged=tags.has(id),relation_node=has(relation_nodes,node_count,id),odd_degree=degree!=2;
            const bool anchor=endpoint || tagged || relation_node || relation_way || odd_degree;
            receipt[3]=add(receipt[3],1);receipt[7]=add(receipt[7],tagged);receipt[8]=add(receipt[8],relation_node);receipt[9]=add(receipt[9],relation_way);receipt[10]=add(receipt[10],odd_degree);receipt[11]=add(receipt[11],endpoint);
            if(anchor){receipt[4]=add(receipt[4],1);receipt[16]=add(receipt[16],internal);}
        };
        while(!queue.empty()){
            const auto item=queue.top();queue.pop();const auto& row=item.row;
            if(row.node!=id){finish();id=row.node;degree=internal=0;endpoint=relation_way=false;}
            receipt[0]=add(receipt[0],1);need(receipt[0]<=expected_refs,"delivered_reference_cap");
            receipt[1]=add(receipt[1],row.degree);receipt[2]=add(receipt[2],row.flags);degree=add(degree,row.degree);internal=add(internal,row.flags?0:1);endpoint|=row.flags!=0;relation_way|=has(relation_ways,way_count,row.way);
            advance(item.part);
        }
        finish();tags.finish();receipt[12]=tags.rows;
        need(receipt[0]==expected_refs && receipt[2]==2*expected_ways && receipt[1]==2*(expected_refs-expected_ways),"whole_occurrence_accounting");
        receipt[5]=add(expected_ways,receipt[16]);receipt[6]=expected_refs-expected_ways;
        need(receipt[3]<UINT32_MAX && receipt[4]<UINT32_MAX && 2*receipt[5]<UINT32_MAX && add(receipt[6],receipt[5])<UINT32_MAX,"prototype_u32_index_bound");
        receipt[13]=12*receipt[4]+24*receipt[5]+4;receipt[14]=8*receipt[3]+4*receipt[6]+8*receipt[5]+4;receipt[15]=add(receipt[13],receipt[14]);receipt[17]=1;
    },error,size);
}
