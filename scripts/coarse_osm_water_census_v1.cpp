// Count all water-feature metadata through the immutable full-source validator.
// No coordinates, country ID dictionary, selected geometry or map is retained.
#include "coarse_osm_topology_source_v1.cpp"

namespace water_census {
constexpr unsigned width = 40;
class Census {
    Bytes pending_;
    void record(const std::uint8_t* body, std::uint32_t size) {
        Input in{body, size};
        need(in.number(4) == 0x31465047, "water_frame_magic");
        const auto kind = in.number(1);
        need(kind < 3, "water_frame_kind");
        counts[kind] = checked_add(counts[kind], 1);
        // The sealed producer already validates every node field. This census
        // neither projects nor stores national node data.
        if (kind == 0) return;
        need(in.number(1) == 1 && in.number(2) == 0, "water_frame_state");
        const auto identity = in.number(8); in.number(8); in.string();
        const auto tags = in.number(4);
        need(tags <= (size-in.position)/8, "water_tag_count");
        bool natural=false, riverbank=false, reservoir=false, highway=false;
        View type, water;
        std::uint64_t tag_bytes=0;
        for (std::uint64_t i=0; i<tags; ++i) {
            const auto key=in.string(), value=in.string();
            tag_bytes=checked_add(tag_bytes, key.size()+value.size());
            natural |= key=="natural" && value=="water";
            riverbank |= key=="waterway" && value=="riverbank";
            reservoir |= key=="landuse" && value=="reservoir";
            highway |= key=="highway";
            if (key=="type") type=value;
            if (key=="water") water=value;
        }
        const bool selected = natural || riverbank || reservoir;
        if (!selected) return;
        add(17, tag_bytes); add(18, natural); add(19, riverbank); add(20, reservoir);
        static constexpr std::array<View,7> names{{"lake","reservoir","river","pond","basin","canal","lagoon"}};
        auto at=std::find(names.begin(),names.end(),water);
        add(28+(at==names.end()?7:static_cast<unsigned>(at-names.begin())));
        add(14,size);
        if (kind==1) {
            add(3); counts[24]=identity;
            const auto refs=in.number(4);
            need(refs>=2 && refs <= (size-in.position)/8, "water_reference_count");
            std::uint64_t first=0,last=0;
            for (std::uint64_t i=0;i<refs;++i) {last=in.number(8);if(!i)first=last;}
            add(4, refs); add(first==last?5:6); add(23,highway);
            add(36, first==last && refs<4);
            counts[15]=std::max(counts[15], refs);
        } else {
            add(7); counts[25]=identity;
            add(type=="multipolygon"?21:22);
            const auto members=in.number(4);
            need(members <= (size-in.position)/13, "water_member_count");
            counts[16]=std::max(counts[16], members);
            for (std::uint64_t i=0;i<members;++i) {
                const auto member=in.number(1); in.number(8); const auto role=in.string();
                need(member<3,"water_member_type");
                add(member==0?9:member==1?8:10);
                if(member==1) add(role=="outer"?11:role=="inner"?12:13);
            }
        }
        need(in.position==in.size,"water_selected_trailing_bytes");
    }
public:
    std::array<std::uint64_t,width> counts{};
    bool running=false, attempted=false, source_complete=false, finished=false;
    void add(unsigned at,std::uint64_t n=1) {counts[at]=checked_add(counts[at],n);}
    void feed(const std::uint8_t* data,std::uint32_t size) {
        need(!finished && size<=1048576 && pending_.size()+size<=9437188,"water_semantic_buffer_cap");
        pending_.insert(pending_.end(),data,data+size);
        std::size_t cursor=0;
        while(pending_.size()-cursor>=4) {
            Input length{pending_.data()+cursor,4};const auto n=length.number(4);
            need(n && n<=8388608,"water_semantic_frame_cap");
            if(pending_.size()-cursor-4<n)break;
            record(pending_.data()+cursor+4,static_cast<std::uint32_t>(n));cursor+=4+n;
        }
        if(cursor)pending_.erase(pending_.begin(),pending_.begin()+cursor);
    }
    void finish() {
        need(!running && source_complete && !finished && pending_.empty(),"water_complete_source_required");
        counts[26]=1;finished=true;
    }
};
thread_local std::unique_ptr<Census> active;
struct Capture {Callback callback;void* user;std::string failure;};
int callback(void* user,std::uint32_t event,const std::uint8_t* data,std::uint32_t size) {
    auto& captured=*static_cast<Capture*>(user);
    try {if(event==0)active->feed(data,size);return captured.callback(captured.user,event,data,size);}
    catch(const Failure& error){captured.failure=error.message;}
    catch(const std::exception& error){captured.failure=error.what();}
    catch(...){captured.failure="water_consumer_failure";}
    return -1;
}
template<class Action> int capture(Action action,std::uint32_t mode,Callback outer,void* user,std::uint64_t* receipt,char* error,std::uint32_t size) noexcept {
    try {
        need(active && !active->running && !active->attempted && !active->finished && mode<=1 && outer && receipt && error && size && size<=1024,"water_capture_configuration");
        Capture state{outer,user,{}};active->running=true;active->attempted=true;
        const auto code=action(callback,&state);active->running=false;
        if(!state.failure.empty()){error_text(error,size,state.failure.c_str());receipt[4]=0;return -2;}
        active->source_complete=code==0 && receipt[4]==1;return code;
    } catch(const Failure& failure){error_text(error,size,failure.message);}
    catch(...){error_text(error,size,"water_capture_failure");}
    if(active)active->running=false;
    if(receipt)receipt[4]=0;
    return -2;
}
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_water_census_abi() noexcept{return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_water_census_begin() noexcept {
    try {if(water_census::active)return -1;water_census::active=std::make_unique<water_census::Census>();return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_census_finish(std::uint64_t* out,std::uint32_t words,char* error,std::uint32_t size) noexcept {
    if(!out || words!=water_census::width || !error || !size || size>1024)return -1;
    std::fill(out,out+words,0);
    try {need(bool(water_census::active),"water_missing_census");water_census::active->finish();std::copy(water_census::active->counts.begin(),water_census::active->counts.end(),out);return 0;}
    catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_finish_failure");}return -2;
}
extern "C" __attribute__((visibility("default"))) void gp_water_census_release() noexcept {
    if(!water_census::active || !water_census::active->running)water_census::active.reset();
}
extern "C" __attribute__((visibility("default"))) int gp_water_census_frames(const std::uint8_t* data,std::uint64_t bytes,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept {
    if(!receipt || receipt_count!=receipt_size)return -1;
    return water_census::capture([&](Callback sink,void* state){return gp_country_screen_frames(data,bytes,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},mode,outer,user,receipt,error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_census_pbf(const char* path,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept {
    if(!receipt || receipt_count!=receipt_size)return -1;
    return water_census::capture([&](Callback sink,void* state){return gp_country_screen_pbf(path,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},mode,outer,user,receipt,error,size);
}
