// Lossless selected GPF way stream and sorted unique native node IDs.
// This adds no coordinates or polygon/routing policy.
#include "coarse_osm_water_union_v1.cpp"

namespace water_references {
constexpr std::size_t chunk=1048576;
constexpr std::uint64_t reference_cap=150000000;
class Capture {
    Bytes pending_,output_;
    std::vector<std::uint64_t> members_,nodes_;
    std::size_t member_cursor_=0;
    std::uint64_t expected_ways_,expected_refs_,previous_way_=0;
    void flush(){
        if(output_.empty())return;
        need(sink && sink(user,20,output_.data(),output_.size())==0,"water_refs_output_callback");
        ++counts[4];output_.clear();
    }
    void append(const std::uint8_t* data,std::size_t size){
        while(size){const auto n=std::min(size,chunk-output_.size());output_.insert(output_.end(),data,data+n);
            data+=n;size-=n;if(output_.size()==chunk)flush();}
    }
    void record(const std::uint8_t* body,std::uint32_t size){
        Input in{body,size};need(in.number(4)==0x31465047,"water_refs_magic");
        const auto kind=in.number(1);need(kind<3,"water_refs_kind");if(kind!=1)return;
        need(in.number(1)==1 && in.number(2)==0,"water_refs_state");
        const auto identity=in.number(8);in.number(8);in.string();
        need(identity>previous_way_,"water_refs_way_order");previous_way_=identity;
        while(member_cursor_<members_.size() && members_[member_cursor_]<identity)++member_cursor_;
        const bool member=member_cursor_<members_.size() && members_[member_cursor_]==identity;
        if(member)++member_cursor_;
        const auto tags=in.number(4);need(tags<=(size-in.position)/8,"water_refs_tag_count");
        bool water=false;
        for(std::uint64_t i=0;i<tags;++i){const auto key=in.string(),value=in.string();
            water|=(key=="natural" && value=="water") || (key=="waterway" && value=="riverbank") || (key=="landuse" && value=="reservoir");}
        if(!water && !member)return;
        const auto refs=in.number(4);need(refs>=2 && refs<=(size-in.position)/8,"water_refs_reference_count");
        need(counts[0]<expected_ways_ && refs<=expected_refs_-nodes_.size(),"water_refs_frozen_dimensions");
        for(std::uint64_t i=0;i<refs;++i)nodes_.push_back(in.number(8));
        need(in.position==in.size,"water_refs_selected_trailing");
        std::uint8_t prefix[4];for(unsigned i=0;i<4;++i)prefix[i]=static_cast<std::uint8_t>(size>>(8*i));
        append(prefix,4);append(body,size);++counts[0];counts[1]+=refs;counts[2]+=4+size;
    }
public:
    std::array<std::uint64_t,8> counts{};
    Callback sink=nullptr;void* user=nullptr;
    bool running=false,attempted=false,complete=false,finished=false,finish_attempted=false;
    Capture(const std::uint64_t* ids,std::uint32_t count,std::uint64_t ways,std::uint64_t refs):expected_ways_(ways),expected_refs_(refs){
        need(count<=1000000 && (!count || ids) && ways<=4000000 && refs<=reference_cap,"water_refs_input_cap");
        if(count)members_.assign(ids,ids+count);
        std::uint64_t previous=0;for(auto id:members_){need(id>previous && id<(std::uint64_t(1)<<63),"water_refs_member_order_domain");previous=id;}
        nodes_.reserve(refs);output_.reserve(chunk);
    }
    void feed(const std::uint8_t* data,std::uint32_t size){
        need(!finished && size<=chunk && pending_.size()+size<=9437188,"water_refs_pending_cap");
        pending_.insert(pending_.end(),data,data+size);std::size_t cursor=0;
        while(pending_.size()-cursor>=4){Input length{pending_.data()+cursor,4};const auto n=length.number(4);
            need(n && n<=8388608,"water_refs_frame_cap");if(pending_.size()-cursor-4<n)break;
            record(pending_.data()+cursor+4,n);cursor+=4+n;}
        if(cursor)pending_.erase(pending_.begin(),pending_.begin()+cursor);
    }
    void source_end(bool success){complete=success;if(success)flush();sink=nullptr;user=nullptr;}
    void finish(Callback callback,void* context){
        need(!running && complete && !finished && !finish_attempted && pending_.empty() && callback && counts[0]==expected_ways_ && nodes_.size()==expected_refs_,"water_refs_complete_source_required");
        finish_attempted=true;
        std::sort(nodes_.begin(),nodes_.end());nodes_.erase(std::unique(nodes_.begin(),nodes_.end()),nodes_.end());
        counts[3]=nodes_.size();
        for(std::size_t cursor=0;cursor<nodes_.size();){const auto n=std::min(chunk/8,nodes_.size()-cursor);
            need(callback(context,21,reinterpret_cast<const std::uint8_t*>(nodes_.data()+cursor),n*8)==0,"water_refs_node_callback");
            cursor+=n;++counts[5];}
        counts[6]=1;finished=true;
    }
};
thread_local std::unique_ptr<Capture> active;
struct Forward{Callback callback;void* user;std::string failure;};
int callback(void* user,std::uint32_t event,const std::uint8_t* data,std::uint32_t size){
    auto& state=*static_cast<Forward*>(user);
    try{if(event==0)active->feed(data,size);return state.callback(state.user,event,data,size);}
    catch(const Failure& error){state.failure=error.message;}catch(const std::exception& error){state.failure=error.what();}catch(...){state.failure="water_refs_callback_failure";}return -1;
}
template<class Action> int capture(Action action,Callback outer,void* user,std::uint64_t* receipt,char* error,std::uint32_t size) noexcept{
    try{need(active && !active->running && !active->attempted && !active->finished && outer && receipt && error && size && size<=1024,"water_refs_capture_configuration");
        Forward state{outer,user,{}};active->running=true;active->attempted=true;active->sink=outer;active->user=user;
        const auto code=action(callback,&state);active->running=false;
        if(!state.failure.empty()){error_text(error,size,state.failure.c_str());receipt[4]=0;active->source_end(false);return -2;}
        active->source_end(code==0 && receipt[4]==1);return code;
    }catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_refs_capture_failure");}
    if(active){active->running=false;active->source_end(false);}if(receipt)receipt[4]=0;return -2;
}

// The independent audit supplies references decoded from saved GPF by Python.
// This utility only sorts integer batches; it shares no GPF selection/parser.
thread_local std::unique_ptr<std::vector<std::uint64_t>> audit_nodes;
thread_local std::uint64_t audit_expected=0;
thread_local bool audit_finished=false;
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_water_refs_abi() noexcept{return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_water_refs_begin(const std::uint64_t* ids,std::uint32_t count,std::uint64_t ways,std::uint64_t refs) noexcept{
    try{if(water_references::active || water_references::audit_nodes)return -1;
        auto next=std::make_unique<water_references::Capture>(ids,count,ways,refs);if(gp_water_union_begin(ids,count)!=0)return -1;
        water_references::active=std::move(next);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_refs_finish(std::uint64_t* out,std::uint32_t words,Callback sink,void* user,char* error,std::uint32_t size) noexcept{
    if(!out || words!=8 || !sink || !error || !size || size>1024)return -1;std::fill(out,out+words,0);
    try{need(bool(water_references::active),"water_refs_missing_session");water_references::active->finish(sink,user);
        std::copy(water_references::active->counts.begin(),water_references::active->counts.end(),out);return 0;}
    catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_refs_finish_failure");}return -2;
}
extern "C" __attribute__((visibility("default"))) void gp_water_refs_release() noexcept{
    if(!water_references::active || !water_references::active->running){water_references::active.reset();gp_water_union_release();}
}
extern "C" __attribute__((visibility("default"))) int gp_water_refs_frames(const std::uint8_t* data,std::uint64_t bytes,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept{
    if(!receipt || receipt_count!=receipt_size)return -1;
    return water_references::capture([&](Callback sink,void* state){return gp_water_union_frames(data,bytes,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},outer,user,receipt,error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_refs_pbf(const char* path,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept{
    if(!receipt || receipt_count!=receipt_size)return -1;
    return water_references::capture([&](Callback sink,void* state){return gp_water_union_pbf(path,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},outer,user,receipt,error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_refs_audit_begin(std::uint64_t expected) noexcept{
    try{if(water_references::active || water_union::active || water_references::audit_nodes || expected>water_references::reference_cap)return -1;
        auto nodes=std::make_unique<std::vector<std::uint64_t>>();nodes->reserve(expected);
        water_references::audit_expected=expected;water_references::audit_finished=false;water_references::audit_nodes=std::move(nodes);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_refs_audit_append(const std::uint64_t* ids,std::uint32_t count) noexcept{
    try{auto& nodes=water_references::audit_nodes;if(!nodes || water_references::audit_finished || !count || !ids || count>131072 || nodes->size()+count>water_references::audit_expected)return -1;
        for(std::uint32_t i=0;i<count;++i)if(!ids[i] || ids[i]>=(std::uint64_t(1)<<63))return -1;
        nodes->insert(nodes->end(),ids,ids+count);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_refs_audit_finish(Callback sink,void* user,std::uint64_t* count) noexcept{
    try{auto& nodes=water_references::audit_nodes;if(!nodes || water_references::audit_finished || !sink || !count || nodes->size()!=water_references::audit_expected)return -1;
        water_references::audit_finished=true;
        std::sort(nodes->begin(),nodes->end());nodes->erase(std::unique(nodes->begin(),nodes->end()),nodes->end());*count=nodes->size();
        for(std::size_t cursor=0;cursor<nodes->size();){const auto n=std::min(water_references::chunk/8,nodes->size()-cursor);
            if(sink(user,22,reinterpret_cast<const std::uint8_t*>(nodes->data()+cursor),n*8)!=0)return -2;cursor+=n;}return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) void gp_water_refs_audit_release() noexcept{water_references::audit_nodes.reset();water_references::audit_expected=0;water_references::audit_finished=false;}
