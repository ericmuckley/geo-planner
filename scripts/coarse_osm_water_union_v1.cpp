// Count every tagged-water way UNION source-derived relation-member way.
// The immutable water/source validators still inspect and seal every object.
#include "coarse_osm_water_census_v1.cpp"

namespace water_union {
constexpr unsigned width=20;
class Census {
    Bytes pending_;
    std::vector<std::uint64_t> ids_;
    std::size_t cursor_=0;
    std::uint64_t previous_way_=0;
    void record(const std::uint8_t* body,std::uint32_t size) {
        Input in{body,size};
        need(in.number(4)==0x31465047,"water_union_magic");
        const auto kind=in.number(1);
        need(kind<3,"water_union_kind");
        if(kind!=1)return;
        need(in.number(1)==1 && in.number(2)==0,"water_union_state");
        const auto identity=in.number(8);in.number(8);in.string();
        need(identity>previous_way_,"water_union_way_order");previous_way_=identity;
        while(cursor_<ids_.size() && ids_[cursor_]<identity)missing.push_back(ids_[cursor_++]);
        const bool member=cursor_<ids_.size() && ids_[cursor_]==identity;
        if(member)++cursor_;
        const auto tags=in.number(4);
        need(tags<=(size-in.position)/8,"water_union_tag_count");
        bool tagged=false;
        for(std::uint64_t i=0;i<tags;++i) {
            const auto key=in.string(),value=in.string();
            tagged |= (key=="natural" && value=="water") || (key=="waterway" && value=="riverbank") || (key=="landuse" && value=="reservoir");
        }
        if(!tagged && !member)return;
        const auto refs=in.number(4);
        need(refs>=2 && refs<=(size-in.position)/8,"water_union_reference_count");
        std::uint64_t first=0,last=0;
        for(std::uint64_t i=0;i<refs;++i){last=in.number(8);if(!i)first=last;}
        need(in.position==in.size,"water_union_selected_trailing");
        add(0);add(1,refs);add(first==last?2:3);add(13,size);
        counts[12]=std::max(counts[12],refs);counts[16]=identity;
        if(!counts[15])counts[15]=identity;
        if(tagged){add(4);add(5,refs);}
        if(member){add(6);add(7,refs);}
        if(tagged && member){add(8);add(9,refs);}
        if(member && !tagged){add(10);add(11,refs);}
    }
public:
    std::array<std::uint64_t,width> counts{};
    std::vector<std::uint64_t> missing;
    bool running=false,attempted=false,complete=false,finished=false;
    Census(const std::uint64_t* ids,std::uint32_t count) {
        need(count<=1000000 && (!count || ids),"water_union_member_input_cap");
        if(count)ids_.assign(ids,ids+count);
        std::uint64_t previous=0;
        for(auto id:ids_){need(id>previous && id<(std::uint64_t(1)<<63),"water_union_member_id_order_domain");previous=id;}
        counts[17]=count;
    }
    void add(unsigned at,std::uint64_t value=1){counts[at]=checked_add(counts[at],value);}
    void feed(const std::uint8_t* data,std::uint32_t size) {
        need(!finished && size<=1048576 && pending_.size()+size<=9437188,"water_union_pending_cap");
        pending_.insert(pending_.end(),data,data+size);
        std::size_t cursor=0;
        while(pending_.size()-cursor>=4){
            Input length{pending_.data()+cursor,4};const auto n=length.number(4);
            need(n && n<=8388608,"water_union_frame_cap");
            if(pending_.size()-cursor-4<n)break;
            record(pending_.data()+cursor+4,static_cast<std::uint32_t>(n));cursor+=4+n;
        }
        if(cursor)pending_.erase(pending_.begin(),pending_.begin()+cursor);
    }
    void finish(){
        need(!running && complete && !finished && pending_.empty(),"water_union_complete_source_required");
        while(cursor_<ids_.size())missing.push_back(ids_[cursor_++]);
        counts[14]=missing.size();
        need(counts[6]+counts[14]==counts[17] && counts[0]==counts[4]+counts[10] && counts[1]==counts[5]+counts[11] &&
             counts[6]==counts[8]+counts[10] && counts[7]==counts[9]+counts[11],"water_union_exact_set_accounting");
        counts[18]=1;finished=true;
    }
};
thread_local std::unique_ptr<Census> active;
struct Capture{Callback callback;void* user;std::string failure;};
int callback(void* user,std::uint32_t event,const std::uint8_t* data,std::uint32_t size){
    auto& state=*static_cast<Capture*>(user);
    try{if(event==0)active->feed(data,size);return state.callback(state.user,event,data,size);}
    catch(const Failure& error){state.failure=error.message;}catch(const std::exception& error){state.failure=error.what();}catch(...){state.failure="water_union_callback_failure";}
    return -1;
}
template<class Action> int capture(Action action,Callback outer,void* user,std::uint64_t* receipt,char* error,std::uint32_t size) noexcept {
    try{
        need(active && !active->running && !active->attempted && !active->finished && outer && receipt && error && size && size<=1024,"water_union_capture_configuration");
        Capture state{outer,user,{}};active->running=true;active->attempted=true;
        const auto code=action(callback,&state);active->running=false;
        if(!state.failure.empty()){error_text(error,size,state.failure.c_str());receipt[4]=0;return -2;}
        active->complete=code==0 && receipt[4]==1;return code;
    }catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_union_capture_failure");}
    if(active)active->running=false;
    if(receipt)receipt[4]=0;
    return -2;
}
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_water_union_abi() noexcept{return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_water_union_begin(const std::uint64_t* ids,std::uint32_t count) noexcept{
    try{if(water_union::active)return -1;auto next=std::make_unique<water_union::Census>(ids,count);
        if(gp_water_census_begin()!=0)return -1;water_union::active=std::move(next);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_union_finish(std::uint64_t* out,std::uint32_t words,char* error,std::uint32_t size) noexcept{
    if(!out || words!=water_union::width || !error || !size || size>1024)return -1;
    std::fill(out,out+words,0);
    try{need(bool(water_union::active),"water_union_missing_session");water_union::active->finish();
        std::copy(water_union::active->counts.begin(),water_union::active->counts.end(),out);return 0;}
    catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_union_finish_failure");}return -2;
}
extern "C" __attribute__((visibility("default"))) int gp_water_union_missing(std::uint64_t* out,std::uint32_t count) noexcept{
    if(!water_union::active || !water_union::active->finished || water_union::active->missing.size()!=count || (count && !out))return -1;
    if(count)std::copy(water_union::active->missing.begin(),water_union::active->missing.end(),out);return 0;
}
extern "C" __attribute__((visibility("default"))) void gp_water_union_release() noexcept{
    if(!water_union::active || !water_union::active->running){water_union::active.reset();gp_water_census_release();}
}
extern "C" __attribute__((visibility("default"))) int gp_water_union_frames(const std::uint8_t* data,std::uint64_t bytes,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept{
    if(!receipt || receipt_count!=receipt_size)return -1;
    return water_union::capture([&](Callback sink,void* state){return gp_water_census_frames(data,bytes,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},outer,user,receipt,error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_union_pbf(const char* path,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept{
    if(!receipt || receipt_count!=receipt_size)return -1;
    return water_union::capture([&](Callback sink,void* state){return gp_water_census_pbf(path,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},outer,user,receipt,error,size);
}
