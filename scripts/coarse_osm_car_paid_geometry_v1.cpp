// Paid-geometry format. The included source readers/math are frozen prerequisites.
#include "coarse_osm_car_geometry_native_v1.cpp"
#include "coarse_osm_car_cost_math_v1.hpp"

namespace {
constexpr double TIME_TOLERANCE_MS=10000;
constexpr uint64_t PAID_OUTPUT_LIMIT=48ull<<20;
struct Projection {double distance,fraction;};
double paid_longitude_delta(const Point& a,const Point& b) {
    int64_t delta=int64_t(b.x)-a.x;
    if (delta>1800000000ll) delta-=3600000000ll;
    if (delta<-1800000000ll) delta+=3600000000ll;
    return delta/1e7*RAD;
}
double paid_angle(const Point& a,const Point& b) {
    double dy=std::sin((int64_t(b.y)-a.y)/1e7*RAD/2),dx=std::sin(paid_longitude_delta(a,b)/2);
    return 2*std::asin(std::min(1.0,std::sqrt(dy*dy+std::cos(a.lat)*std::cos(b.lat)*dx*dx)));
}
double paid_bearing(const Point& a,const Point& b) {
    double dl=paid_longitude_delta(a,b),half=std::sin(dl/2);
    // Integer coordinate differences and this identity avoid cancellation for
    // short source segments and at the longitude wrap.
    double north=std::sin((int64_t(b.y)-a.y)/1e7*RAD)+std::sin(a.lat)*std::cos(b.lat)*2*half*half;
    return std::atan2(std::sin(dl)*std::cos(b.lat),north);
}
Projection project(const Point& p,const Point& a,const Point& b) {
    double ab=paid_angle(a,b),ap=paid_angle(a,p);
    if (ab<1e-12 || ab>3.14159265358979323846-1e-12) {
        double bp=paid_angle(b,p);return ap<=bp?Projection{EARTH*ap,0}:Projection{EARTH*bp,1};
    }
    double difference=paid_bearing(a,p)-paid_bearing(a,b);
    double along=std::atan2(std::sin(ap)*std::cos(difference),std::cos(ap));
    if (along<=0) return {EARTH*ap,0};
    if (along>=ab) return {EARTH*paid_angle(b,p),1};
    return {EARTH*std::abs(std::asin(std::clamp(std::sin(ap)*std::sin(difference),-1.0,1.0))),along/ab};
}

std::vector<uint32_t> paid_keep(const std::vector<Point>& points,const std::vector<uint64_t>& f,const std::vector<uint64_t>& b,uint64_t& work,double& max_geo,double& max_time) {
    need(points.size()>=2 && points.size()<=1048576 && f.size()==points.size() && b.size()==points.size() && f[0]==0 && b[0]==0,"Paid curve/prefix dimensions");
    for (size_t i=1;i<points.size();i++) need(f[i]>=f[i-1] && b[i]>=b[i-1] && f[i]<=car_cost_math::maximum_ms && b[i]<=car_cost_math::maximum_ms,"Paid prefix range/order");
    std::vector<uint8_t> keep(points.size(),0);keep.front()=keep.back()=1;
    std::vector<std::pair<uint32_t,uint32_t>> stack{{0,uint32_t(points.size()-1)}};
    auto errors=[&](uint32_t i,uint32_t first,uint32_t last) {
        need(++work<=MAX_COMPARISONS,"Paid geometry comparison bound");
        auto p=project(points[i],points[first],points[last]);
        double ef=std::abs(double(f[i]-f[first])-p.fraction*double(f[last]-f[first]));
        double eb=std::abs(double(b[i]-b[first])-p.fraction*double(b[last]-b[first]));
        return std::make_pair(p.distance,std::max(ef,eb));
    };
    while (!stack.empty()) {
        auto [first,last]=stack.back();stack.pop_back();double largest=-1;uint32_t split=first;
        for (uint32_t i=first+1;i<last;i++) {
            auto [geo,time]=errors(i,first,last);double score=std::max(geo/TOLERANCE,time/TIME_TOLERANCE_MS);
            if (score>largest) {largest=score;split=i;}
        }
        if (largest>1) {keep[split]=1;stack.emplace_back(first,split);stack.emplace_back(split,last);}
    }
    std::vector<uint32_t> result;
    for (uint32_t i=0;i<points.size();i++) if (keep[i]) result.push_back(i);
    for (size_t j=1;j<result.size();j++) for (uint32_t i=result[j-1]+1;i<result[j];i++) {
        auto [geo,time]=errors(i,result[j-1],result[j]);
        need(geo<=TOLERANCE+1e-5 && time<=TIME_TOLERANCE_MS+.001,"Paid final interpolation error");
        max_geo=std::max(max_geo,geo);max_time=std::max(max_time,time);
    }
    return result;
}

std::vector<uint32_t> paid_words(const std::string& name,unsigned width) {
    int fd=open(name.c_str(),O_RDONLY|O_NOFOLLOW);need(fd>=0,"Paid packed input open");struct stat state{};
    if (fstat(fd,&state) || !S_ISREG(state.st_mode) || state.st_nlink!=1 || state.st_size<0 || state.st_size>67108864 || state.st_size%width) {
        close(fd);throw std::runtime_error("Paid packed input type/size/shape");
    }
    FILE* stream=fdopen(fd,"rb");if (!stream) {close(fd);throw std::runtime_error("Paid packed input stream");}
    std::vector<uint32_t> result;result.reserve(state.st_size/width);uint8_t bytes[4];
    while (auto count=std::fread(bytes,1,width,stream)) {
        if (count!=width) {fclose(stream);throw std::runtime_error("Paid packed short word");}
        uint32_t value=0;for (unsigned i=0;i<width;i++) value|=uint32_t(bytes[i])<<(8*i);result.push_back(value);
    }
    bool ok=!std::ferror(stream);int code=fclose(stream);need(ok && code==0,"Paid packed input read/close");return result;
}
double paid_double(const uint8_t* p) {uint64_t bits=u64(p);double value;std::memcpy(&value,&bits,8);return value;}
void append_varint(std::vector<uint8_t>& out,uint32_t value) {
    while (value>=128) {out.push_back(uint8_t(value)|128);value>>=7;}out.push_back(value);
}
void append_delta(std::vector<uint8_t>& out,int32_t value,int32_t previous) {
    uint32_t delta=uint32_t(value)-uint32_t(previous);append_varint(out,(delta<<1)^(delta&0x80000000u?UINT32_MAX:0));
}
uint16_t fraction(uint64_t prefix,uint64_t total) {
    if (!total) {need(prefix==0,"Paid disabled prefix");return 0;}
    need(prefix<=total,"Paid prefix total");return uint16_t((prefix*65535+total/2)/total);
}
struct CurveRecord {uint32_t arc,start,end,position_start,position_end,way,first,last;int8_t direction;};
struct LongRecord {uint32_t arc,units,way,first,last;int8_t direction;};
struct PaidOverflow {uint32_t key,value;};
struct PaidWriter {
    std::string root;uint64_t total=0;
    explicit PaidWriter(std::string value):root(std::move(value)) {}
    template<class Value> void write(const std::string& name,uint64_t count,unsigned width,Value value) {
        need(width>=1 && width<=4 && count<=67108864/width && total+count*width<=PAID_OUTPUT_LIMIT,"Paid output field/total bound");
        File output(root+"/"+name,true);uint8_t bytes[4];
        for (uint64_t i=0;i<count;i++) {
            uint32_t word=value(i);need(width==4 || word<(1u<<(8*width)),"Paid output word range");
            for (unsigned j=0;j<width;j++) bytes[j]=word>>(8*j);
            need(std::fwrite(bytes,1,width,output.stream)==width,"Paid output write");
        }
        output.finish();total+=count*width;
    }
};

void paid_build(const std::string& root,const std::string& offset_name,const std::string& map_name,const std::string& output,const uint64_t* expected,uint64_t* counts,double* values) {
    uint64_t nodes=expected[0],vertices=expected[1],ways_count=expected[2],refs=expected[3],pre=expected[4],post=expected[5];
    need(nodes>0 && nodes<=64000000 && vertices>0 && vertices<=0xffffff && ways_count>0 && ways_count<=8000000 && refs<=64000000 && post<=pre && pre<=0xffffff,"Paid source dimensions");
    std::vector<std::array<int32_t,2>> xy;xy.reserve(nodes);
    rows<8>(root,"xy",nodes,[&](const uint8_t* p,uint64_t){int32_t x=int32_t(u32(p)),y=int32_t(u32(p+4));point(x,y);xy.push_back({x,y});});need(xy.size()==nodes,"Paid coordinate count");
    std::vector<uint32_t> geometry;geometry.reserve(refs);
    rows<4>(root,"geometry",refs,[&](const uint8_t* p,uint64_t){uint32_t n=u32(p);need(n<nodes,"Paid geometry node range");geometry.push_back(n);});need(geometry.size()==refs,"Paid geometry reference count");
    std::vector<uint32_t> anchors;anchors.reserve(vertices);
    rows<4>(root,"anchors",vertices,[&](const uint8_t* p,uint64_t){uint32_t n=u32(p);need(n<nodes && (anchors.empty() || n>anchors.back()),"Paid anchor order/range");anchors.push_back(n);});need(anchors.size()==vertices,"Paid anchor count");
    std::vector<uint64_t> ids;std::vector<uint32_t> ends;std::vector<std::array<double,2>> speeds;ids.reserve(ways_count);ends.reserve(ways_count);speeds.reserve(ways_count);
    rows<32>(root,"ways",ways_count,[&](const uint8_t* p,uint64_t){
        uint64_t id=u64(p);uint32_t end=u32(p+28),flags=u32(p+24);double f=paid_double(p+8),b=paid_double(p+16);
        need(id>0 && (ids.empty() || id>ids.back()) && end<=refs && (ends.empty() || end>=ends.back()),"Paid way order/end");
        need(std::isfinite(f) && std::isfinite(b) && f>=0 && f<=160 && b>=0 && b<=160 && bool(flags&1)==(f>0) && bool(flags&2)==(b>0),"Paid source speeds/directions");
        ids.push_back(id);ends.push_back(end);speeds.push_back({f,b});
    });need(ids.size()==ways_count && ends.back()==refs,"Paid way count/end");
    std::vector<uint8_t> blocked(ways_count,0);uint64_t prior_closed=0;
    rows<8>(root,"closures",2000000,[&](const uint8_t* p,uint64_t){uint64_t id=u64(p);need(id>prior_closed,"Paid closure order");prior_closed=id;auto at=std::lower_bound(ids.begin(),ids.end(),id);if (at!=ids.end() && *at==id) blocked[at-ids.begin()]=1;});
    auto offsets=paid_words(offset_name,3),arc_map=paid_words(map_name,4);
    need(offsets.size()==vertices+1 && offsets[0]==0 && offsets.back()==post && arc_map.size()==post,"Paid parent CSR/map shape");
    for (size_t i=0;i<vertices;i++) need(offsets[i]<=offsets[i+1],"Paid parent CSR order");
    std::vector<uint8_t> seen((post+7)/8,0);
    for (auto arc:arc_map) {need(arc<post && !(seen[arc>>3]&(1<<(arc&7))),"Paid arc map bijection");seen[arc>>3]|=1<<(arc&7);}
    std::vector<uint8_t>().swap(seen);std::vector<uint32_t> cursor(offsets.begin(),offsets.end()-1);
    std::vector<CurveRecord> curves;std::vector<LongRecord> longs;std::vector<uint8_t> packets;std::vector<uint32_t> positions;
    std::array<uint32_t,3> prior{};int previous_direction=0;bool expect_pair=false;uint32_t pair_csr=0;uint64_t pair_ms=0;
    counts[0]=nodes;counts[1]=vertices;counts[2]=ways_count;counts[3]=refs;
    auto budget=[&] {need(packets.size()+positions.size()*4+curves.size()*23+longs.size()*21+7*counts[12]+4<=PAID_OUTPUT_LIMIT,"Paid geometry serialized output budget");};
    rows<32>(root,"arcs",pre,[&](const uint8_t* p,uint64_t){
        counts[4]++;uint32_t tail=u32(p),head=u32(p+4),way=u32(p+8),first=u32(p+12),last=u32(p+16);int direction=int8_t(p[20]);uint64_t ms=u64(p+24);
        need(tail<vertices && head<vertices && way<ways_count && first<last && (direction==1 || direction==-1) && !p[21] && !p[22] && !p[23] && ms>0 && ms<=car_cost_math::maximum_ms,"Paid source arc range/padding");
        uint32_t begin=way?ends[way-1]:0;need(last<ends[way]-begin && geometry[begin+first]==anchors[direction==1?tail:head] && geometry[begin+last]==anchors[direction==1?head:tail],"Paid source span/endpoint identity");
        std::array<uint32_t,3> key{way,first,last};bool duplicate=previous_direction && key==prior;
        need(!previous_direction || key>prior || (duplicate && previous_direction==1 && direction==-1),"Paid source arc order");
        if (!duplicate) need(!expect_pair,"Paid missing source reverse arc");prior=key;previous_direction=direction;
        if (blocked[way]) return;
        counts[5]++;uint32_t csr=cursor[tail]++;need(csr<offsets[tail+1],"Paid source CSR row correspondence");
        if (duplicate) {need(expect_pair && csr==pair_csr && ms==pair_ms,"Paid exact source reverse cost/correspondence");expect_pair=false;return;}
        counts[6]++;bool both=speeds[way][0]>0 && speeds[way][1]>0;
        need((direction==1?speeds[way][0]:speeds[way][1])>0 && (!both || direction==1),"Paid source direction availability");
        uint32_t canonical=arc_map[csr];int canonical_direction=direction;
        if (both) {pair_csr=cursor[head];need(pair_csr<offsets[head+1],"Paid source reverse CSR bound");if (arc_map[pair_csr]<canonical) {canonical=arc_map[pair_csr];canonical_direction=-direction;}expect_pair=true;}
        std::vector<Point> points;std::vector<uint64_t> f{0},b{0};points.reserve(last-first+1);f.reserve(last-first+1);b.reserve(last-first+1);double length=0;
        need(uint64_t(last)-first+1<=1048576,"Paid source curve count bound");
        for (uint32_t i=first;i<=last;i++) {
            uint32_t node=geometry[begin+i];const auto& c=xy[node];auto current=point(c[0],c[1]);
            if (!points.empty()) {
                const auto& old=points.back();bool same=geometry[begin+i-1]==node;length+=EARTH*angle(old,current);
                f.push_back(speeds[way][0]>0?car_cost_math::sum(f.back(),car_cost_math::primitive(old.x,old.y,c[0],c[1],speeds[way][0],same)):0);
                b.push_back(speeds[way][1]>0?car_cost_math::sum(b.back(),car_cost_math::primitive(old.x,old.y,c[0],c[1],speeds[way][1],same)):0);
            }
            points.push_back(current);
        }
        need(ms==(direction==1?f.back():b.back()),"Paid whole source integer-ms cost equality");if (both) pair_ms=b.back();
        values[2]=std::max(values[2],length);auto kept=paid_keep(points,f,b,counts[15],values[0],values[1]);
        if (kept.size()>2) {
            CurveRecord record{canonical,uint32_t(packets.size()),0,uint32_t(positions.size()),0,way,first,last,int8_t(canonical_direction)};
            const auto& start=points[canonical_direction==1?0:points.size()-1];int32_t x=start.x,y=start.y;
            for (size_t j=1;j+1<kept.size();j++) {
                uint32_t i=kept[canonical_direction==1?j:kept.size()-1-j];const auto& q=points[i];append_delta(packets,q.x,x);append_delta(packets,q.y,y);x=q.x;y=q.y;
                uint16_t pf=canonical_direction==1?fraction(f[i],f.back()):fraction(b.back()-b[i],b.back());
                uint16_t pb=canonical_direction==1?fraction(b[i],b.back()):fraction(f.back()-f[i],f.back());
                packets.push_back(pf);packets.push_back(pf>>8);packets.push_back(pb);packets.push_back(pb>>8);positions.push_back(first+i);
            }
            record.end=packets.size();record.position_end=positions.size();curves.push_back(record);counts[8]+=kept.size()-2;
        }
        if (length>SHORT_SPAN) {double units=std::ceil(length/8)+1;need(units<=UINT32_MAX,"Paid length-unit overflow bound");longs.push_back({canonical,uint32_t(units),way,first,last,int8_t(canonical_direction)});counts[12]+=units>=65535;}
        budget();
    });
    need(!expect_pair && counts[4]==pre && counts[5]==post,"Paid complete source arc/pair counts");
    for (size_t i=0;i<vertices;i++) need(cursor[i]==offsets[i+1],"Paid complete source CSR correspondence");
    std::sort(curves.begin(),curves.end(),[](const auto& a,const auto& b){return a.arc<b.arc;});
    std::sort(longs.begin(),longs.end(),[](const auto& a,const auto& b){return a.arc<b.arc;});
    std::vector<uint8_t> ordered;ordered.reserve(packets.size());std::vector<uint32_t> ordered_positions,packet_offsets{0};ordered_positions.reserve(positions.size());
    for (size_t i=0;i<curves.size();i++) {const auto& r=curves[i];need(!i || r.arc>curves[i-1].arc,"Paid unique curve keys");ordered.insert(ordered.end(),packets.begin()+r.start,packets.begin()+r.end);ordered_positions.insert(ordered_positions.end(),positions.begin()+r.position_start,positions.begin()+r.position_end);packet_offsets.push_back(ordered.size());}
    std::vector<PaidOverflow> overflows;
    for (size_t i=0;i<longs.size();i++) {need(!i || longs[i].arc>longs[i-1].arc,"Paid unique long-span keys");if (longs[i].units>=65535) overflows.push_back({longs[i].arc,longs[i].units});}
    PaidWriter writer(output);
    writer.write("curve-keys.u24",curves.size(),3,[&](size_t i){return curves[i].arc;});
    writer.write("curve-offsets.u32",packet_offsets.size(),4,[&](size_t i){return packet_offsets[i];});
    writer.write("curve-packets.u8",ordered.size(),1,[&](size_t i){return ordered[i];});
    writer.write("long-keys.u24",longs.size(),3,[&](size_t i){return longs[i].arc;});
    writer.write("long-lengths.u16",longs.size(),2,[&](size_t i){return std::min(longs[i].units,65535u);});
    writer.write("long-overflow-keys.u24",overflows.size(),3,[&](size_t i){return overflows[i].key;});
    writer.write("long-overflow-units.u32",overflows.size(),4,[&](size_t i){return overflows[i].value;});
    counts[10]=writer.total;
    auto provenance=[&](const auto& records,const std::string& name) {
        writer.write(name,records.size()*4,4,[&](size_t i){const auto& r=records[i/4];switch (i%4) {case 0:return r.way;case 1:return r.first;case 2:return r.last;default:return r.direction==1?1u:255u;}});
    };
    provenance(curves,"curve-source.bin");provenance(longs,"long-source.bin");
    writer.write("curve-source-positions.u32",ordered_positions.size(),4,[&](size_t i){return ordered_positions[i];});
    need(writer.total<=PAID_OUTPUT_LIMIT,"Paid total output budget");
    counts[7]=curves.size();counts[9]=longs.size();counts[11]=writer.total-counts[10];counts[12]=overflows.size();counts[13]=ordered.size();counts[14]=writer.total;
}
}

extern "C" __attribute__((visibility("default"))) uint32_t gp_car_paid_geometry_abi() {return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_car_paid_project(const int32_t* xy,double* result,char* error,size_t size) {
    try {need(xy && result,"Paid projection pointers");auto value=project(point(xy[0],xy[1]),point(xy[2],xy[3]),point(xy[4],xy[5]));result[0]=value.distance;result[1]=value.fraction;return 0;}
    catch (const std::exception& e) {if (error && size) std::snprintf(error,size,"%s",e.what());return 1;}
}
extern "C" __attribute__((visibility("default"))) int gp_car_paid_simplify(const int32_t* xy,uint32_t count,const uint64_t* f,const uint64_t* b,uint8_t* flags,uint64_t* work,double* errors,char* error,size_t size) {
    try {need(xy && f && b && flags && work && errors && count>=2 && count<=1048576,"Paid simplify pointers/count");std::vector<Point> points;points.reserve(count);for (uint32_t i=0;i<count;i++) points.push_back(point(xy[2ull*i],xy[2ull*i+1]));std::vector<uint64_t> forward(f,f+count),backward(b,b+count);*work=0;errors[0]=errors[1]=0;auto kept=paid_keep(points,forward,backward,*work,errors[0],errors[1]);std::fill(flags,flags+count,0);for (auto i:kept) flags[i]=1;return 0;}
    catch (const std::exception& e) {if (error && size) std::snprintf(error,size,"%s",e.what());return 1;}
}
extern "C" __attribute__((visibility("default"))) int gp_car_paid_geometry_build(const char* source,const char* offsets,const char* arc_map,const char* output,const uint64_t* expected,uint64_t* counts,double* values,char* error,size_t size) {
    try {need(source && offsets && arc_map && output && expected && counts && values,"Paid geometry pointers");std::fill(counts,counts+16,0);std::fill(values,values+3,0);paid_build(source,offsets,arc_map,output,expected,counts,values);return 0;}
    catch (const std::exception& e) {if (error && size) std::snprintf(error,size,"%s",e.what());return 1;}
}
