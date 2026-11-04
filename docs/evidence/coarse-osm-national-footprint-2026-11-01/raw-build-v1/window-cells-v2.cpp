// Exact ID-gap runs with canonical raw fallback; coordinates/cell values unchanged.
#include <algorithm>
#include <array>
#include <cstdint>

extern "C" int gp_delta_decode(const std::uint8_t*,std::uint32_t,std::uint32_t,std::int64_t,std::int64_t,std::int64_t*,std::int32_t*,std::uint32_t) noexcept;
namespace {
constexpr std::uint64_t max_id=0x7fffffffffffffffULL;
constexpr std::uint32_t max_rows=4096,max_queries=65536,head=32;
using Ids=std::array<std::int64_t,max_rows>;
using Cells=std::array<std::uint16_t,max_rows>;
void put(std::uint8_t* p,std::uint64_t value,unsigned bytes) noexcept {
    for(unsigned k=0;k<bytes;++k)p[k]=static_cast<std::uint8_t>(value>>(8*k));
}
std::uint64_t get(const std::uint8_t* p,unsigned bytes) noexcept {
    std::uint64_t value=0;for(unsigned k=0;k<bytes;++k)value|=static_cast<std::uint64_t>(p[k])<<(8*k);return value;
}
std::uint32_t var_size(std::uint64_t value) noexcept {
    std::uint32_t n=1;while(value>>=7)++n;return n;
}
std::uint32_t variable(std::uint8_t* out,std::uint64_t value) noexcept {
    std::uint32_t n=0;do{auto byte=static_cast<std::uint8_t>(value&127);value>>=7;out[n++]=byte|(value?128:0);}while(value);return n;
}
bool read_var(const std::uint8_t* raw,std::uint32_t end,std::uint32_t& p,std::uint64_t& value) noexcept {
    value=0;
    for(unsigned used=0;used<9;++used){
        if(p==end)return false;auto byte=raw[p++];value|=static_cast<std::uint64_t>(byte&127)<<(7*used);
        if(!(byte&128))return value&&(!used||(byte&127));
    }
    return false;
}
struct Sizes {std::uint32_t raw=0,run=0,runs=0;};
Sizes sizes(const Ids& ids,std::uint32_t rows) noexcept {
    Sizes result;std::uint32_t begin=1;
    while(begin<rows){
        auto delta=static_cast<std::uint64_t>(ids[begin])-ids[begin-1];auto end=begin+1;
        while(end<rows&&static_cast<std::uint64_t>(ids[end])-ids[end-1]==delta)++end;
        result.raw+=var_size(delta)*(end-begin);result.run+=var_size(delta)+var_size(end-begin);++result.runs;begin=end;
    }
    return result;
}
bool parse_ids(const std::uint8_t* raw,std::uint32_t begin,std::uint32_t bytes,std::uint32_t rows,
               std::uint64_t first,std::uint64_t last,std::uint32_t runs,bool canonical,Ids& ids) noexcept {
    std::uint32_t p=begin,count=1;std::uint64_t identity=first,previous=0;ids[0]=static_cast<std::int64_t>(first);
    if(runs){
        for(std::uint32_t r=0;r<runs;++r){
            std::uint64_t gap=0,length=0;
            if(!read_var(raw,begin+bytes,p,gap)||!read_var(raw,begin+bytes,p,length)||gap==previous||length>rows-count)return false;
            for(std::uint64_t k=0;k<length;++k){if(gap>max_id-identity)return false;identity+=gap;ids[count++]=static_cast<std::int64_t>(identity);}
            previous=gap;
        }
    }else{
        while(count<rows){std::uint64_t gap=0;if(!read_var(raw,begin+bytes,p,gap)||gap>max_id-identity)return false;
            identity+=gap;ids[count++]=static_cast<std::int64_t>(identity);}
    }
    if(p!=begin+bytes||count!=rows||identity!=last)return false;
    if(canonical){auto s=sizes(ids,rows);
        if(runs){if(s.run>=s.raw||s.run!=bytes||s.runs!=runs)return false;}
        else if(s.raw!=bytes||s.run<s.raw)return false;
    }
    return true;
}
bool parse_cells(const std::uint8_t* raw,std::uint32_t p,std::uint32_t rows,std::uint32_t runs,std::uint32_t cell_count,Cells& cells) noexcept {
    std::uint32_t count=0,previous=cell_count;
    for(std::uint32_t k=0;k<runs;++k){auto cell=get(raw+p,2),length=get(raw+p+2,2);p+=4;
        if(cell>=cell_count||cell==previous||!length||length>rows-count)return false;
        std::fill(cells.begin()+count,cells.begin()+count+length,static_cast<std::uint16_t>(cell));count+=length;previous=cell;}
    return count==rows;
}
bool decode(const std::uint8_t* raw,std::uint32_t bytes,std::uint32_t cell_count,bool legacy,Ids& ids,Cells& cells,std::uint32_t& rows) noexcept {
    const auto h=legacy?28U:head;
    if(!raw||bytes<h||bytes>65536||!cell_count||cell_count>7225)return false;
    rows=static_cast<std::uint32_t>(get(raw,4));auto first=get(raw+4,8),last=get(raw+12,8),id_bytes=get(raw+20,4);
    auto id_runs=legacy?0U:static_cast<std::uint32_t>(get(raw+24,4));auto cell_runs=get(raw+(legacy?24:28),4);
    if(!rows||rows>max_rows||!first||last<first||last>max_id||id_runs>rows-1||!cell_runs||cell_runs>rows||
       id_bytes>9*(rows-1)||id_bytes<(id_runs?2*id_runs:rows-1)||h+id_bytes+4*cell_runs!=bytes)return false;
    return parse_ids(raw,h,static_cast<std::uint32_t>(id_bytes),rows,first,last,id_runs,!legacy,ids)&&
           parse_cells(raw,h+static_cast<std::uint32_t>(id_bytes),rows,static_cast<std::uint32_t>(cell_runs),cell_count,cells);
}
bool encode(const Ids& ids,const Cells& cells,std::uint32_t rows,std::uint8_t* out,std::uint32_t capacity,std::uint32_t* written) noexcept {
    auto s=sizes(ids,rows);const bool use_runs=s.run<s.raw;auto id_bytes=use_runs?s.run:s.raw;
    std::uint32_t cell_runs=0;for(std::uint32_t k=0;k<rows;++k)if(!k||cells[k]!=cells[k-1])++cell_runs;
    const auto required=head+id_bytes+4*cell_runs;if(required>capacity)return false;
    put(out,rows,4);put(out+4,ids[0],8);put(out+12,ids[rows-1],8);put(out+20,id_bytes,4);put(out+24,use_runs?s.runs:0,4);put(out+28,cell_runs,4);
    std::uint32_t p=head;
    if(use_runs){
        std::uint32_t begin=1;
        while(begin<rows){auto gap=static_cast<std::uint64_t>(ids[begin])-ids[begin-1];auto end=begin+1;
            while(end<rows&&static_cast<std::uint64_t>(ids[end])-ids[end-1]==gap)++end;
            p+=variable(out+p,gap);p+=variable(out+p,end-begin);begin=end;}
    }else for(std::uint32_t k=1;k<rows;++k)p+=variable(out+p,static_cast<std::uint64_t>(ids[k])-ids[k-1]);
    std::uint32_t begin=0;
    while(begin<rows){auto end=begin+1;while(end<rows&&cells[end]==cells[begin])++end;
        put(out+p,cells[begin],2);put(out+p+2,end-begin,2);p+=4;begin=end;}
    *written=p;return true;
}
bool edges(const std::int32_t* values,std::uint32_t count,std::int32_t low,std::int32_t high) noexcept {
    if(!values||!count||count>42)return false;
    for(std::uint32_t k=0;k<count;++k)if(values[k]<low||values[k]>high||(k&&values[k]<=values[k-1]))return false;
    return true;
}
std::uint32_t slot(const std::int32_t* values,std::uint32_t count,std::int32_t value) noexcept {
    auto p=std::lower_bound(values,values+count,value);auto index=static_cast<std::uint32_t>(p-values);
    return 2*index+static_cast<std::uint32_t>(index<count&&values[index]==value);
}
}

extern "C" __attribute__((visibility("default")))
std::uint32_t gp_window_cells_v2_abi() noexcept {return 0x20000;}

extern "C" __attribute__((visibility("default")))
int gp_window_cells_v2_encode(const std::uint8_t* fine,std::uint32_t bytes,std::uint32_t rows,std::int64_t first,std::int64_t last,
                              const std::int32_t* x,std::uint32_t nx,const std::int32_t* y,std::uint32_t ny,
                              std::uint8_t* out,std::uint32_t capacity,std::uint32_t* written) noexcept {
    if(!written)return -1;*written=0;
    if(!out||!edges(x,nx,-1800000000,1800000000)||!edges(y,ny,-900000000,900000000))return -1;
    Ids ids{};Cells cells{};std::array<std::int32_t,2*max_rows> xy{};
    if(gp_delta_decode(fine,bytes,rows,first,last,ids.data(),xy.data(),max_rows)!=0)return -2;
    for(std::uint32_t k=0;k<rows;++k)cells[k]=static_cast<std::uint16_t>(slot(x,nx,xy[2*k])+(2*nx+1)*slot(y,ny,xy[2*k+1]));
    return encode(ids,cells,rows,out,capacity,written)?0:-3;
}

extern "C" __attribute__((visibility("default")))
int gp_window_cells_v2_lookup(const std::uint8_t* raw,std::uint32_t bytes,std::uint32_t cell_count,
                              const std::int64_t* queries,std::uint32_t count,std::uint16_t* out,std::uint32_t capacity) noexcept {
    if(!queries||!out||!count||count>max_queries||capacity<count)return -1;
    Ids ids{};Cells cells{};std::uint32_t rows=0;if(!decode(raw,bytes,cell_count,false,ids,cells,rows))return -2;
    std::array<std::uint16_t,max_queries> answer{};
    for(std::uint32_t k=0;k<count;++k){if(queries[k]<=0)return -3;
        auto p=std::lower_bound(ids.begin(),ids.begin()+rows,queries[k]);if(p==ids.begin()+rows||*p!=queries[k])return -3;answer[k]=cells[p-ids.begin()];}
    std::copy(answer.begin(),answer.begin()+count,out);return 0;
}

extern "C" __attribute__((visibility("default")))
int gp_window_cells_v2_from_v1(const std::uint8_t* raw,std::uint32_t bytes,std::uint32_t cell_count,
                               std::uint8_t* out,std::uint32_t capacity,std::uint32_t* written) noexcept {
    if(!written)return -1;*written=0;if(!out)return -1;
    Ids ids{},check_ids{};Cells cells{},check_cells{};std::uint32_t rows=0,check_rows=0;
    if(!decode(raw,bytes,cell_count,true,ids,cells,rows))return -2;
    if(!encode(ids,cells,rows,out,capacity,written))return -3;
    if(!decode(out,*written,cell_count,false,check_ids,check_cells,check_rows)||rows!=check_rows)return -4;
    for(std::uint32_t k=0;k<rows;++k)if(ids[k]!=check_ids[k]||cells[k]!=check_cells[k])return -4;
    return 0;
}
