// Geometry capacity probe only. Routing costs/permissions/arrays are unchanged.
#include "coarse_osm_car_packed_native_v1.cpp"
#include <cmath>

namespace {
constexpr double EARTH=6371008.8, RAD=3.141592653589793238462643383279502884/180;
constexpr double TOLERANCE=100, SHORT_SPAN=1000;
constexpr uint64_t MAX_COMPARISONS=500000000;
struct Point { double lon,lat;int32_t x,y; };
Point point(int32_t x,int32_t y) {
    need(x>=-1800000000 && x<=1800000000 && y>=-900000000 && y<=900000000,"Geometry coordinate range");
    return {x/1e7*RAD,y/1e7*RAD,x,y};
}
double angle(const Point& a,const Point& b) {
    double dy=std::sin((b.lat-a.lat)/2),dx=std::sin((b.lon-a.lon)/2);
    return 2*std::asin(std::min(1.0,std::sqrt(dy*dy+std::cos(a.lat)*std::cos(b.lat)*dx*dx)));
}
double bearing(const Point& a,const Point& b) {
    return std::atan2(std::sin(b.lon-a.lon)*std::cos(b.lat),std::cos(a.lat)*std::sin(b.lat)-std::sin(a.lat)*std::cos(b.lat)*std::cos(b.lon-a.lon));
}
double point_segment(const Point& p,const Point& a,const Point& b) {
    double ab=angle(a,b),ap=angle(a,p);
    if (ab<1e-12 || ab>3.14159265358979323846-1e-12) return EARTH*std::min(ap,angle(b,p));
    double difference=bearing(a,p)-bearing(a,b);
    double along=std::atan2(std::sin(ap)*std::cos(difference),std::cos(ap));
    if (along<0 || along>ab) return EARTH*std::min(ap,angle(b,p));
    return EARTH*std::abs(std::asin(std::clamp(std::sin(ap)*std::sin(difference),-1.0,1.0)));
}
std::vector<uint32_t> simplify(const std::vector<Point>& points,double tolerance,uint64_t& work,double& error) {
    need(points.size()>=2 && points.size()<=1048576 && std::isfinite(tolerance) && tolerance>0,"Geometry curve/tolerance bound");
    std::vector<uint8_t> keep(points.size(),0);keep.front()=keep.back()=1;
    std::vector<std::pair<uint32_t,uint32_t>> stack{{0,uint32_t(points.size()-1)}};
    auto distance=[&](uint32_t i,uint32_t first,uint32_t last) {
        need(++work<=MAX_COMPARISONS,"Geometry comparison bound");return point_segment(points[i],points[first],points[last]);
    };
    while (!stack.empty()) {
        auto [first,last]=stack.back();stack.pop_back();double largest=-1;uint32_t split=first;
        for (uint32_t i=first+1;i<last;i++) {double value=distance(i,first,last);if (value>largest) {largest=value;split=i;}}
        if (largest>tolerance) {keep[split]=1;stack.emplace_back(first,split);stack.emplace_back(split,last);}
    }
    std::vector<uint32_t> result;
    for (uint32_t i=0;i<points.size();i++) if (keep[i]) result.push_back(i);
    for (size_t j=1;j<result.size();j++) for (uint32_t i=result[j-1]+1;i<result[j];i++) {
        double value=distance(i,result[j-1],result[j]);need(value<=tolerance+1e-5,"Geometry final simplification error");error=std::max(error,value);
    }
    return result;
}
uint64_t varint_bytes(uint32_t word) {uint64_t bytes=1;while (word>=128) {word>>=7;bytes++;}return bytes;}
uint64_t coordinate_bytes(const std::vector<Point>& points,const std::vector<uint32_t>& kept,bool reverse_order) {
    const auto& first=points[reverse_order?kept.back():kept.front()];int32_t x=first.x,y=first.y;uint64_t total=0;
    for (size_t i=1;i+1<kept.size();i++) {
        const auto& p=points[kept[reverse_order?kept.size()-1-i:i]];
        for (uint32_t delta:{uint32_t(p.x)-uint32_t(x),uint32_t(p.y)-uint32_t(y)}) total+=varint_bytes((delta<<1)^(delta&0x80000000u?UINT32_MAX:0));
        x=p.x;y=p.y;
    }
    return total;
}
void probe(const std::string& root,const uint64_t* expected,uint64_t* out,double* values) {
    const uint64_t nodes=expected[0],vertices=expected[1],way_count=expected[2],references=expected[3],pre=expected[4],post=expected[5];
    need(nodes>0 && nodes<=64000000 && vertices>0 && vertices<=0xffffff && way_count<=8000000 && references<=64000000 && post<=pre && pre<=0xffffff,"Geometry declared dimensions");
    std::vector<std::array<int32_t,2>> xy;xy.reserve(nodes);
    rows<8>(root,"xy",nodes,[&](const uint8_t* p,uint64_t){int32_t x=int32_t(u32(p)),y=int32_t(u32(p+4));point(x,y);xy.push_back({x,y});});need(xy.size()==nodes,"Geometry selected coordinate count");out[0]=xy.size();
    std::vector<uint32_t> geometry;geometry.reserve(references);
    rows<4>(root,"geometry",references,[&](const uint8_t* p,uint64_t){uint32_t index=u32(p);need(index<nodes,"Geometry reference range");geometry.push_back(index);});need(geometry.size()==references,"Geometry reference count");out[1]=geometry.size();
    std::vector<uint32_t> anchors;anchors.reserve(vertices);
    rows<4>(root,"anchors",vertices,[&](const uint8_t* p,uint64_t){uint32_t index=u32(p);need(index<nodes && (anchors.empty() || index>anchors.back()),"Geometry anchor range/order");anchors.push_back(index);});need(anchors.size()==vertices,"Geometry anchor count");
    std::vector<uint64_t> way_ids;way_ids.reserve(way_count);std::vector<uint32_t> ends;ends.reserve(way_count);
    rows<32>(root,"ways",way_count,[&](const uint8_t* p,uint64_t){uint64_t id=u64(p);uint32_t end=u32(p+28);need(id>0 && (way_ids.empty() || id>way_ids.back()) && end<=references && (ends.empty() || end>=ends.back()),"Geometry way bounds/order");way_ids.push_back(id);ends.push_back(end);});
    need(way_ids.size()==way_count && !ends.empty() && ends.back()==references,"Geometry way/end count");out[2]=way_ids.size();
    std::vector<uint8_t> blocked(way_count,0);uint64_t previous_closed=0;
    rows<8>(root,"closures",2000000,[&](const uint8_t* p,uint64_t){uint64_t id=u64(p);need(id>previous_closed,"Geometry closure order");previous_closed=id;auto found=std::lower_bound(way_ids.begin(),way_ids.end(),id);if (found!=way_ids.end() && *found==id) blocked[found-way_ids.begin()]=1;});
    std::array<uint32_t,3> prior{};int previous_direction=0;
    constexpr std::array<double,11> thresholds{100,250,500,1000,2500,5000,10000,25000,50000,100000,std::numeric_limits<double>::infinity()};
    rows<32>(root,"arcs",pre,[&](const uint8_t* p,uint64_t){
        out[3]++;uint32_t tail=u32(p),head=u32(p+4),way=u32(p+8),first=u32(p+12),last=u32(p+16);int direction=int8_t(p[20]);
        need(tail<vertices && head<vertices && way<way_count && first<last && (direction==1 || direction==-1) && !p[21] && !p[22] && !p[23] && u64(p+24)>0,"Geometry arc fact range/padding");
        uint32_t begin=way?ends[way-1]:0;need(last<ends[way]-begin,"Geometry span source-way positions");
        need(geometry[begin+first]==anchors[direction==1?tail:head] && geometry[begin+last]==anchors[direction==1?head:tail],"Geometry source endpoints/native anchor identity");
        std::array<uint32_t,3> key{way,first,last};need(!previous_direction || key>prior || (key==prior && previous_direction==1 && direction==-1),"Geometry source arc order");
        bool duplicate=previous_direction && key==prior;prior=key;previous_direction=direction;
        if (blocked[way]) return;out[4]++;if (duplicate) return;
        out[5]++;std::vector<Point> curve;curve.reserve(last-first+1);double length=0;
        for (uint32_t i=first;i<=last;i++) {const auto& coords=xy[geometry[begin+i]];auto current=point(coords[0],coords[1]);if (!curve.empty()) length+=EARTH*angle(curve.back(),current);curve.push_back(current);}
        values[0]+=length;values[1]=std::max(values[1],length);out[6]+=curve.size()-2;out[9]+=length>SHORT_SPAN;out[10]+=length==0;out[11]=std::max(out[11],uint64_t(curve.size()));
        size_t bin=0;while (length>thresholds[bin]) bin++;out[17+bin]++;
        auto kept=simplify(curve,TOLERANCE,out[13],values[2]);out[7]+=kept.size()-2;out[8]+=kept.size()>2;out[12]=std::max(out[12],uint64_t(kept.size()));
        out[14]+=std::max(coordinate_bytes(curve,kept,false),coordinate_bytes(curve,kept,true));
    });
    need(out[3]==pre && out[4]==post,"Geometry pre/post closure count");
    out[15]=out[14]+4*out[7]+7*out[8]+4;out[16]=19*out[9];
}
}
extern "C" __attribute__((visibility("default"))) uint32_t gp_car_geometry_abi() {return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_car_geometry_distance(const int32_t* xy,double* result,char* error,size_t size) {
    try {need(xy && result,"Geometry distance pointers");*result=point_segment(point(xy[0],xy[1]),point(xy[2],xy[3]),point(xy[4],xy[5]));return 0;}
    catch (const std::exception& e) {if (error && size) std::snprintf(error,size,"%s",e.what());return 1;}
}
extern "C" __attribute__((visibility("default"))) int gp_car_geometry_simplify(const int32_t* xy,uint32_t count,double tolerance,uint8_t* flags,uint64_t* work,double* error_m,char* error,size_t size) {
    try {need(xy && flags && work && error_m && count>=2 && count<=1048576,"Geometry simplify pointers/count");std::vector<Point> points;points.reserve(count);for (uint32_t i=0;i<count;i++) points.push_back(point(xy[2ull*i],xy[2ull*i+1]));*work=0;*error_m=0;auto kept=simplify(points,tolerance,*work,*error_m);std::fill(flags,flags+count,0);for (auto i:kept) flags[i]=1;return 0;}
    catch (const std::exception& e) {if (error && size) std::snprintf(error,size,"%s",e.what());return 1;}
}
extern "C" __attribute__((visibility("default"))) int gp_car_geometry_probe(const char* source,const uint64_t* expected,uint64_t* counts,double* values,char* error,size_t size) {
    try {need(source && expected && counts && values,"Geometry probe pointers");std::fill(counts,counts+28,0);std::fill(values,values+3,0);probe(source,expected,counts,values);return 0;}
    catch (const std::exception& e) {if (error && size) std::snprintf(error,size,"%s",e.what());return 1;}
}
