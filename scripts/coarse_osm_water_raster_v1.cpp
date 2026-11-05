// Exact integer/rational raster data from already validated planar source rings.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <vector>

namespace {
using Wide=__int128;
struct Point { uint64_t id; int32_t x,y; };
struct XY { int32_t x,y; };
struct Ring { uint32_t start,count,parent; uint8_t role; };
struct Crossing { Wide numerator; int64_t denominator; uint32_t row; };
constexpr uint64_t MAX_CELLS=61360000,MAX_POINTS=2000000,MAX_CROSSINGS=4000000;
struct Raster {
    int64_t x=0,y=0,step=0;
    uint32_t width=0,height=0,expected_rings=0,expected_points=0;
    uint64_t features=0,rings=0,points=0,boxes=0,incomplete_boxes=0,max_crossings=0;
    bool active=false,failed=false,finished=false;
    Point first{},previous{};
    Wide area=0;
    std::vector<uint8_t> water,uncertain;
    std::vector<XY> vertices;
    std::vector<Ring> boundaries;
    std::vector<Crossing> crossings;
};
Raster grid;
void need(bool okay,const char* text) {if(!okay)throw std::runtime_error(text);}
Wide floor_div(Wide a,Wide b) {need(b>0,"raster denominator");return a>=0?a/b:-((-a+b-1)/b);}
Wide ceil_div(Wide a,Wide b) {return -floor_div(-a,b);}
template<class F> int guarded(F fn,char* error,uint32_t size) noexcept {
    try {need(!grid.failed,"raster failed state requires release");fn();if(error && size)error[0]=0;return 0;}
    catch(const std::exception& failure) {grid.failed=true;if(error && size){std::strncpy(error,failure.what(),size-1);error[size-1]=0;}return -1;}
    catch(...) {grid.failed=true;if(error && size){std::strncpy(error,"raster unknown failure",size-1);error[size-1]=0;}return -2;}
}
void range(std::vector<uint8_t>& plane,uint32_t row,Wide low,Wide high) {
    if(low>high || high<0 || low>=grid.width)return;
    const uint64_t a=uint64_t(row)*grid.width+uint64_t(std::max(Wide(0),low));
    const uint64_t b=uint64_t(row)*grid.width+uint64_t(std::min(Wide(grid.width-1),high));
    const uint64_t first=a/8,last=b/8;
    if(first==last) {plane[first]|=uint8_t((255u<<(a%8)) & (255u>>(7-b%8)));return;}
    plane[first]|=uint8_t(255u<<(a%8));
    std::fill(plane.begin()+first+1,plane.begin()+last,uint8_t(255));
    plane[last]|=uint8_t(255u>>(7-b%8));
}
void centers(uint32_t row,Wide low,Wide high,Wide denominator) {
    const Wide base=Wide(2*grid.x+grid.step)*denominator;
    const Wide scale=Wide(2)*grid.step*denominator;
    range(grid.water,row,ceil_div(2*low-base,scale),floor_div(2*high-base,scale));
}
void edge(XY a,XY b) {
    if(a.y>b.y)std::swap(a,b);
    const int64_t dx=int64_t(b.x)-a.x,dy=int64_t(b.y)-a.y;
    const auto first=std::max(Wide(0),ceil_div(Wide(a.y)-grid.y,grid.step)-1);
    const auto last=std::min(Wide(grid.height-1),floor_div(Wide(b.y)-grid.y,grid.step));
    for(Wide row=first;row<=last;++row) {
        const int64_t low_y=std::max(int64_t(a.y),grid.y+int64_t(row)*grid.step);
        const int64_t high_y=std::min(int64_t(b.y),grid.y+(int64_t(row)+1)*grid.step);
        Wide low,high,denominator;
        if(dy==0) {low=std::min(a.x,b.x);high=std::max(a.x,b.x);denominator=1;}
        else {
            low=Wide(a.x)*dy+Wide(dx)*(low_y-a.y);high=Wide(a.x)*dy+Wide(dx)*(high_y-a.y);denominator=dy;
            if(low>high)std::swap(low,high);
        }
        // Closed cell/segment intersection: include both sides of grid lines
        // and every cell touched at a corner, without rounding a clipped edge.
        range(grid.uncertain,uint32_t(row),ceil_div(low-Wide(grid.x)*denominator,Wide(grid.step)*denominator)-1,
              floor_div(high-Wide(grid.x)*denominator,Wide(grid.step)*denominator));
        const int64_t cy2=2*(grid.y+int64_t(row)*grid.step)+grid.step;
        if(cy2<2*int64_t(a.y) || cy2>2*int64_t(b.y))continue;
        if(dy==0) {if(cy2==2*int64_t(a.y))centers(uint32_t(row),low,high,1);}
        else {
            const Wide num=Wide(2)*a.x*dy+Wide(dx)*(cy2-2*int64_t(a.y));
            const Wide offset=num-Wide(2*grid.x+grid.step)*dy;
            const Wide unit=Wide(2)*grid.step*dy;
            if(offset%unit==0)range(grid.water,uint32_t(row),offset/unit,offset/unit);
        }
    }
    if(dy==0)return;
    const auto start=std::max(Wide(0),ceil_div(Wide(2)*(int64_t(a.y)-grid.y)-grid.step,Wide(2)*grid.step));
    const auto stop=std::min(Wide(grid.height-1),ceil_div(Wide(2)*(int64_t(b.y)-grid.y)-grid.step,Wide(2)*grid.step)-1);
    for(Wide row=start;row<=stop;++row) {
        need(grid.crossings.size()<MAX_CROSSINGS,"raster per-feature crossing cap");
        const int64_t cy2=2*(grid.y+int64_t(row)*grid.step)+grid.step;
        grid.crossings.push_back({Wide(2)*a.x*dy+Wide(dx)*(cy2-2*int64_t(a.y)),2*dy,uint32_t(row)});
    }
}
}

extern "C" __attribute__((visibility("default"))) uint32_t gp_wgrid_abi() {return 0x10000;}
extern "C" __attribute__((visibility("default"))) void gp_wgrid_release() noexcept {grid=Raster{};}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_begin(int64_t x,int64_t y,uint32_t step,uint32_t width,uint32_t height,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(grid.water.empty() && width && height && step && uint64_t(width)*height<=MAX_CELLS,"raster fresh grid/dimension cap");
        need(x>=-1800000000 && y>=-900000000 && x+int64_t(width)*step<=1800000000 && y+int64_t(height)*step<=900000000,"raster grid E7 domain");
        grid.x=x;grid.y=y;grid.step=step;grid.width=width;grid.height=height;
        const auto bytes=(uint64_t(width)*height+7)/8;grid.water.resize(bytes);grid.uncertain.resize(bytes);
        grid.vertices.reserve(MAX_POINTS);grid.boundaries.reserve(100000);grid.crossings.reserve(MAX_CROSSINGS);
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_feature(uint32_t rings,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(!grid.water.empty() && !grid.active && !grid.finished && rings>0 && rings<=100000,"raster feature state/rings");
        grid.active=true;grid.expected_rings=rings;grid.expected_points=0;grid.vertices.clear();grid.boundaries.clear();grid.crossings.clear();
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_ring(uint8_t role,uint32_t parent,uint32_t points,char* error,uint32_t size) noexcept {
    return guarded([&]{
        const auto rank=grid.boundaries.size();
        need(grid.active && grid.expected_points==0 && rank<grid.expected_rings && role<=1 && points>=4 && grid.vertices.size()+points<=MAX_POINTS,"raster ring state/fields/cap");
        need((role==0 && parent==rank)||(role==1 && parent<rank && grid.boundaries[parent].role==0),"raster source ring role/parent");
        grid.boundaries.push_back({uint32_t(grid.vertices.size()),points,parent,role});grid.expected_points=points;grid.area=0;
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_points(const Point* points,uint32_t count,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(grid.active && points && count>0 && count<=65536 && count<=grid.expected_points,"raster bounded source point chunk/state");
        const auto& ring=grid.boundaries.back();
        for(uint32_t i=0;i<count;++i) {
            const auto& p=points[i];
            need(p.id>0 && p.id<(uint64_t(1)<<63) && p.x>=-1800000000 && p.x<=1800000000 && p.y>=-900000000 && p.y<=900000000,"raster exact native/E7 point fields");
            if(grid.vertices.size()==ring.start)grid.first=p;
            else {grid.area+=Wide(grid.previous.x)*p.y-Wide(p.x)*grid.previous.y;need(std::abs(int64_t(p.x)-grid.previous.x)<=1800000000,"raster unsupported antimeridian edge");}
            grid.previous=p;grid.vertices.push_back({p.x,p.y});--grid.expected_points;
        }
        if(!grid.expected_points) {
            need(grid.previous.id==grid.first.id && grid.previous.x==grid.first.x && grid.previous.y==grid.first.y,"raster exact native/coordinate closure");
            need((ring.role==0 && grid.area>0)||(ring.role==1 && grid.area<0),"raster accepted-source orientation/nonzero area");
        }
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_feature_finish(char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(grid.active && !grid.expected_points && grid.boundaries.size()==grid.expected_rings,"raster complete source feature");
        for(const auto& ring:grid.boundaries)for(uint32_t i=ring.start;i+1<ring.start+ring.count;++i)edge(grid.vertices[i],grid.vertices[i+1]);
        std::sort(grid.crossings.begin(),grid.crossings.end(),[](const Crossing& a,const Crossing& b){return a.row!=b.row?a.row<b.row:a.numerator*b.denominator<b.numerator*a.denominator;});
        size_t cursor=0;
        while(cursor<grid.crossings.size()) {
            const auto row=grid.crossings[cursor].row;size_t stop=cursor;
            while(stop<grid.crossings.size() && grid.crossings[stop].row==row)++stop;
            need((stop-cursor)%2==0,"raster accepted-source scanline parity");
            for(size_t i=cursor;i<stop;i+=2) {
                const auto& a=grid.crossings[i];const auto& b=grid.crossings[i+1];
                const Wide base=2*grid.x+grid.step,unit=2*grid.step;
                range(grid.water,row,ceil_div(2*a.numerator-base*a.denominator,unit*a.denominator),
                      floor_div(2*b.numerator-base*b.denominator,unit*b.denominator));
            }
            cursor=stop;
        }
        grid.max_crossings=std::max(grid.max_crossings,uint64_t(grid.crossings.size()));
        ++grid.features;grid.rings+=grid.boundaries.size();grid.points+=grid.vertices.size();grid.active=false;
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_box(int32_t x1,int32_t y1,int32_t x2,int32_t y2,uint8_t complete,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(!grid.water.empty() && !grid.active && !grid.finished && x1<=x2 && y1<=y2 && complete<=1,"raster excluded box fields/state");
        need(x1>=-1800000000 && x2<=1800000000 && y1>=-900000000 && y2<=900000000,"raster excluded box E7 domain");
        const auto first=std::max(Wide(0),ceil_div(Wide(y1)-grid.y,grid.step)-1);
        const auto last=std::min(Wide(grid.height-1),floor_div(Wide(y2)-grid.y,grid.step));
        for(Wide row=first;row<=last;++row)range(grid.uncertain,uint32_t(row),ceil_div(Wide(x1)-grid.x,grid.step)-1,floor_div(Wide(x2)-grid.x,grid.step));
        ++grid.boxes;grid.incomplete_boxes+=!complete;
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_finish(uint64_t features,uint64_t rings,uint64_t points,uint64_t boxes,uint64_t incomplete,char* error,uint32_t size) noexcept {
    return guarded([&]{
        need(!grid.water.empty() && !grid.active && !grid.finished && grid.features==features && grid.rings==rings && grid.points==points && grid.boxes==boxes && grid.incomplete_boxes==incomplete,"raster complete declared population");
        std::vector<XY>().swap(grid.vertices);std::vector<Ring>().swap(grid.boundaries);std::vector<Crossing>().swap(grid.crossings);grid.finished=true;
    },error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_copy(uint8_t plane,uint8_t* target,uint64_t bytes) noexcept {
    if(grid.failed || !grid.finished || plane>1 || !target || bytes!=grid.water.size())return -1;
    const auto& source=plane==0?grid.water:grid.uncertain;std::memcpy(target,source.data(),bytes);return 0;
}
extern "C" __attribute__((visibility("default"))) int gp_wgrid_stats(uint64_t* out,uint32_t count) noexcept {
    if(!out || count!=11)return -1;
    out[0]=grid.features;out[1]=grid.rings;out[2]=grid.points;out[3]=grid.boxes;out[4]=grid.incomplete_boxes;out[5]=grid.max_crossings;
    out[6]=grid.water.size()+grid.uncertain.size();out[7]=grid.water.capacity()+grid.uncertain.capacity()+grid.vertices.capacity()*sizeof(XY)+grid.boundaries.capacity()*sizeof(Ring)+grid.crossings.capacity()*sizeof(Crossing);
    out[8]=grid.finished;out[9]=grid.failed;out[10]=grid.active;return 0;
}
