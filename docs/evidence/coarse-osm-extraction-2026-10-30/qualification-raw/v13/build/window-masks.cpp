// Independent conservative primary-table and audit-half-plane predicates.
#include <cstdint>

namespace {
bool shape(const std::uint16_t* cells,std::uint32_t refs,const std::uint32_t* ends,std::uint32_t ways,
           std::uint32_t count,std::uint32_t* out,std::uint32_t capacity) noexcept {
    if(!cells||!ends||!out||!refs||refs>65536||!ways||ways>32768||capacity<ways||!count||count>7225)return false;
    std::uint32_t before=0;
    for(std::uint32_t k=0;k<ways;++k){if(ends[k]<before+2||ends[k]>refs)return false;before=ends[k];}
    if(before!=refs)return false;
    for(std::uint32_t k=0;k<refs;++k)if(cells[k]>=count)return false;
    return true;
}
}
extern "C" __attribute__((visibility("default")))
std::uint32_t gp_window_masks_abi() noexcept {return 0x10000;}

extern "C" __attribute__((visibility("default")))
int gp_window_primary_masks(const std::uint8_t* table,std::uint32_t bytes,std::uint32_t windows,std::uint32_t count,
                            const std::uint16_t* cells,std::uint32_t refs,const std::uint32_t* ends,std::uint32_t ways,
                            std::uint32_t* out,std::uint32_t capacity) noexcept {
    if(!table||!windows||windows>21||bytes!=windows*count||!shape(cells,refs,ends,ways,count,out,capacity))return -1;
    for(std::uint32_t k=0;k<bytes;++k)if(table[k]>15)return -1;
    std::uint32_t begin=0;const auto all=(1U<<windows)-1;
    for(std::uint32_t way=0;way<ways;++way){
        std::uint32_t mask=0;
        for(std::uint32_t p=begin+1;p<ends[way]&&mask!=all;++p){
            const auto* a=table+cells[p-1]*windows;const auto* b=table+cells[p]*windows;
            for(std::uint32_t w=0;w<windows;++w)if(!(a[w]&b[w]))mask|=1U<<w;
        }
        out[way]=mask;begin=ends[way];
    }
    return 0;
}

extern "C" __attribute__((visibility("default")))
int gp_window_audit_masks(const std::uint16_t* boxes,std::uint32_t windows,std::uint32_t width,std::uint32_t height,
                          const std::uint16_t* cells,std::uint32_t refs,const std::uint32_t* ends,std::uint32_t ways,
                          std::uint32_t* out,std::uint32_t capacity) noexcept {
    if(!boxes||!windows||windows>21||width<3||width>85||height<3||height>85||!(width&1)||!(height&1)||
       !shape(cells,refs,ends,ways,width*height,out,capacity))return -1;
    for(std::uint32_t w=0;w<windows;++w){
        const auto* b=boxes+4*w;
        if(!b[0]||!(b[0]&1)||!b[1]||!(b[1]&1)||!(b[2]&1)||!(b[3]&1)||b[0]>b[2]||b[2]>=width-1||b[1]>b[3]||b[3]>=height-1)return -1;
    }
    std::uint32_t begin=0;
    for(std::uint32_t way=0;way<ways;++way){
        std::uint32_t mask=0;
        for(std::uint32_t w=0;w<windows;++w){
            const auto* b=boxes+4*w;
            for(std::uint32_t p=begin+1;p<ends[way];++p){
                const auto x0=cells[p-1]%width,y0=cells[p-1]/width,x1=cells[p]%width,y1=cells[p]/width;
                const bool outside=(x0<b[0]&&x1<b[0])||(x0>b[2]&&x1>b[2])||(y0<b[1]&&y1<b[1])||(y0>b[3]&&y1>b[3]);
                if(!outside){mask|=1U<<w;break;}
            }
        }
        out[way]=mask;begin=ends[way];
    }
    return 0;
}
