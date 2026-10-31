// Compact ID/cell blocks only. Python owns the envelope SHA256 and file contract.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>

extern "C" int gp_delta_decode(const std::uint8_t*,std::uint32_t,std::uint32_t,std::int64_t,std::int64_t,std::int64_t*,std::int32_t*,std::uint32_t) noexcept;
namespace {
constexpr std::uint64_t max_id=0x7fffffffffffffffULL;
constexpr std::uint32_t max_rows=4096,max_queries=65536,head=28;
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
bool edges(const std::int32_t* values,std::uint32_t count,std::int32_t low,std::int32_t high) noexcept {
    if(!values||!count||count>42)return false;
    for(std::uint32_t k=0;k<count;++k)if(values[k]<low||values[k]>high||(k&&values[k]<=values[k-1]))return false;
    return true;
}
std::uint32_t slot(const std::int32_t* values,std::uint32_t count,std::int32_t value) noexcept {
    auto p=std::lower_bound(values,values+count,value);auto index=static_cast<std::uint32_t>(p-values);
    return 2*index+static_cast<std::uint32_t>(index<count&&values[index]==value);
}
bool decode(const std::uint8_t* raw,std::uint32_t bytes,std::uint32_t cell_count,
            std::array<std::int64_t,max_rows>& ids,std::array<std::uint16_t,max_rows>& cells,std::uint32_t& rows) noexcept {
    if(!raw||bytes<head||bytes>65536||!cell_count||cell_count>7225)return false;
    rows=static_cast<std::uint32_t>(get(raw,4));auto first=get(raw+4,8),last=get(raw+12,8);
    auto id_bytes=get(raw+20,4),runs=get(raw+24,4);
    if(!rows||rows>max_rows||!first||last<first||last>max_id||!runs||runs>rows||id_bytes>9*(rows-1)||id_bytes<rows-1||head+id_bytes+4*runs!=bytes)return false;
    std::uint32_t position=head;auto identity=first;ids[0]=static_cast<std::int64_t>(identity);
    for(std::uint32_t k=1;k<rows;++k){
        std::uint64_t delta=0;unsigned used=0;
        for(;used<9;++used){
            if(position==head+id_bytes)return false;
            auto byte=raw[position++];delta|=static_cast<std::uint64_t>(byte&127)<<(7*used);
            if(!(byte&128)){if(used&&!(byte&127))return false;break;}
        }
        if(used==9||!delta||delta>max_id-identity)return false;
        identity+=delta;ids[k]=static_cast<std::int64_t>(identity);
    }
    if(position!=head+id_bytes||identity!=last)return false;
    std::uint32_t count=0,previous=cell_count;
    for(std::uint32_t k=0;k<runs;++k){
        auto cell=get(raw+position,2),length=get(raw+position+2,2);position+=4;
        if(cell>=cell_count||cell==previous||!length||length>rows-count)return false;
        std::fill(cells.begin()+count,cells.begin()+count+length,static_cast<std::uint16_t>(cell));count+=length;previous=cell;
    }
    return count==rows;
}
}

extern "C" __attribute__((visibility("default")))
std::uint32_t gp_window_cells_abi() noexcept {return 0x10000;}

extern "C" __attribute__((visibility("default")))
int gp_window_cells_encode(const std::uint8_t* fine,std::uint32_t bytes,std::uint32_t rows,std::int64_t first,std::int64_t last,
                           const std::int32_t* x,std::uint32_t nx,const std::int32_t* y,std::uint32_t ny,
                           std::uint8_t* out,std::uint32_t capacity,std::uint32_t* written) noexcept {
    if(!written)return -1;*written=0;
    if(!out||!edges(x,nx,-1800000000,1800000000)||!edges(y,ny,-900000000,900000000))return -1;
    std::array<std::int64_t,max_rows> ids{};std::array<std::int32_t,2*max_rows> xy{};
    if(gp_delta_decode(fine,bytes,rows,first,last,ids.data(),xy.data(),max_rows)!=0)return -2;
    std::array<std::uint16_t,max_rows> cells{};std::uint32_t id_bytes=0,runs=0;
    for(std::uint32_t k=0;k<rows;++k){
        cells[k]=static_cast<std::uint16_t>(slot(x,nx,xy[2*k])+(2*nx+1)*slot(y,ny,xy[2*k+1]));
        if(k)id_bytes+=var_size(static_cast<std::uint64_t>(ids[k])-ids[k-1]);
        if(!k||cells[k]!=cells[k-1])++runs;
    }
    const auto required=head+id_bytes+4*runs;if(required>capacity)return -3;
    put(out,rows,4);put(out+4,first,8);put(out+12,last,8);put(out+20,id_bytes,4);put(out+24,runs,4);
    std::uint32_t position=head;
    for(std::uint32_t k=1;k<rows;++k)position+=variable(out+position,static_cast<std::uint64_t>(ids[k])-ids[k-1]);
    std::uint32_t begin=0;
    while(begin<rows){auto end=begin+1;while(end<rows&&cells[end]==cells[begin])++end;
        put(out+position,cells[begin],2);put(out+position+2,end-begin,2);position+=4;begin=end;}
    *written=position;return 0;
}

extern "C" __attribute__((visibility("default")))
int gp_window_cells_lookup(const std::uint8_t* raw,std::uint32_t bytes,std::uint32_t cell_count,
                           const std::int64_t* queries,std::uint32_t count,std::uint16_t* out,std::uint32_t capacity) noexcept {
    if(!queries||!out||!count||count>max_queries||capacity<count)return -1;
    std::array<std::int64_t,max_rows> ids{};std::array<std::uint16_t,max_rows> cells{};std::uint32_t rows=0;
    if(!decode(raw,bytes,cell_count,ids,cells,rows))return -2;
    std::array<std::uint16_t,max_queries> answer{};
    for(std::uint32_t k=0;k<count;++k){
        if(queries[k]<=0)return -3;
        auto p=std::lower_bound(ids.begin(),ids.begin()+rows,queries[k]);
        if(p==ids.begin()+rows||*p!=queries[k])return -3;
        answer[k]=cells[p-ids.begin()];
    }
    std::copy(answer.begin(),answer.begin()+count,out);return 0;
}
