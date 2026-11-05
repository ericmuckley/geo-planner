// Compare static car policies through the immutable full-source validator.
// Persist only changed source IDs/tags; no node coordinates/reference dictionary.
#include "coarse_osm_topology_source_v1.cpp"
#include "coarse_osm_car_native_policy_v3.hpp"
#include <fcntl.h>
#include <unistd.h>

namespace conditional_census {
constexpr unsigned width = 56;
constexpr std::uint64_t output_limit = 48ULL*1048576, record_limit = 250000;
class Census {
    Bytes pending_;
    int output_ = -1;
    std::uint64_t outputLimit_,recordLimit_;
    void append(const Bytes& body) {
        need(counts[18]<recordLimit_ && body.size()<=8388608 && body.size()+4<=outputLimit_-counts[20],"conditional_output_cap");
        Bytes encoded;put32(encoded,static_cast<std::uint32_t>(body.size()));encoded.insert(encoded.end(),body.begin(),body.end());
        std::size_t at=0;
        while(at<encoded.size()) {const auto n=::write(output_,encoded.data()+at,encoded.size()-at);need(n>0,"conditional_output_write");at+=n;}
        add(18);add(20,encoded.size());counts[21]=std::max(counts[21],static_cast<std::uint64_t>(encoded.size()));
    }
    void changed(std::uint8_t kind,std::uint64_t identity,const car_policy::Tags& tags) {
        Bytes body{'C','S','T','1',kind,0,0,0};put64(body,identity);put32(body,static_cast<std::uint32_t>(tags.size()));
        for(const auto& item:tags) {text(body,item.first);text(body,item.second);add(19,item.first.size()+item.second.size());}
        append(body);counts[kind==0?22:23]=identity;
    }
    void record(const std::uint8_t* body,std::uint32_t size) {
        Input in{body,size};need(in.number(4)==0x31465047,"conditional_frame_magic");
        const auto kind=in.number(1);need(kind<3,"conditional_frame_kind");add(kind);
        if(kind==2)return; // Relations retain their unchanged source policy.
        need(in.number(1)==1 && in.number(2)==0,"conditional_frame_state");
        const auto identity=in.number(8);in.number(8);in.string();const auto n=in.number(4);
        need(n<=(size-in.position)/8,"conditional_tag_count");car_policy::Tags tags;bool conditional=false,speed=false;
        for(std::uint64_t i=0;i<n;++i) {const auto key=in.string(),value=in.string();tags.emplace_back(key,value);conditional|=car_policy::ends(key,":conditional");
            speed|=key=="maxspeed:conditional" || key=="maxspeed:forward:conditional" || key=="maxspeed:backward:conditional";}
        if(kind==0) {
            const auto before=car_policy::node_flags(tags),after=car_policy_conditional::node_flags(tags);
            need((before&6)==(after&6),"conditional_signal_tagged_preserved");
            if(!(before&1)) {add(10);need(before==after,"conditional_old_unblocked_retained");add(11);}
            add(8,conditional);add(26,bool(before&1));add(27,bool(after&1));add(28,bool(before&4));add(29,bool(before&2));
            if(before!=after) {need((before&1) && !(after&1),"conditional_node_only_opens");add(9);changed(0,identity,tags);}
            return;
        }
        const auto before=car_policy::way(tags),after=car_policy_conditional::way(tags);
        add(32+before.reason);add(42+after.reason);need(before.role==after.role,"conditional_same_profile");
        if(before.reason==car_policy::outside_profile)return;
        add(3);add(4,before.reason==car_policy::eligible);add(5,after.reason==car_policy::eligible);
        add(12,conditional);add(13,speed);add(16,speed && after.reason!=car_policy::eligible);add(17,conditional && before.reason!=car_policy::eligible);
        const auto refs=in.number(4);need(refs>=2 && refs<=(size-in.position)/8,"conditional_major_reference_count");add(30,refs);
        if(before.reason==car_policy::eligible) {
            need(after.reason==before.reason && after.directions==before.directions && after.default_mask==before.default_mask && after.forward==before.forward && after.backward==before.backward,"conditional_old_eligible_exact");add(7);
        } else if(after.reason==car_policy::eligible) {add(6);add(speed?14:15);changed(1,identity,tags);}
        for(const auto& item:tags)add(31,car_policy_conditional::ignored(item.first));
    }
public:
    std::array<std::uint64_t,width> counts{};
    bool running=false, attempted=false, source_complete=false, finished=false;
    explicit Census(const char* output,std::uint64_t bytes,std::uint64_t records):outputLimit_(bytes),recordLimit_(records) {
        need(bytes>0 && bytes<=output_limit && records>0 && records<=record_limit,"conditional_output_limits");
        need(output && strnlen(output,4097)<=4096,"conditional_output_path");
        output_=::open(output,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);need(output_>=0,"conditional_fresh_output");
    }
    ~Census() {if(output_>=0)::close(output_);}
    void add(unsigned at,std::uint64_t n=1) {counts[at]=checked_add(counts[at],n);}
    void feed(const std::uint8_t* data,std::uint32_t size) {
        need(!finished && size<=1048576 && pending_.size()+size<=9437188,"conditional_semantic_buffer_cap");
        pending_.insert(pending_.end(),data,data+size);
        std::size_t cursor=0;
        while(pending_.size()-cursor>=4) {
            Input length{pending_.data()+cursor,4};const auto n=length.number(4);
            need(n && n<=8388608,"conditional_semantic_frame_cap");
            if(pending_.size()-cursor-4<n)break;
            record(pending_.data()+cursor+4,static_cast<std::uint32_t>(n));cursor+=4+n;
        }
        if(cursor)pending_.erase(pending_.begin(),pending_.begin()+cursor);
    }
    void finish() {
        need(!running && source_complete && !finished && pending_.empty(),"conditional_complete_source_required");
        struct stat state{};need(::fstat(output_,&state)==0 && S_ISREG(state.st_mode) && state.st_nlink==1 && static_cast<std::uint64_t>(state.st_size)==counts[20],"conditional_output_stat");
        const int descriptor=output_;output_=-1;need(::close(descriptor)==0,"conditional_output_close");
        counts[24]=1;finished=true;
    }
};
thread_local std::unique_ptr<Census> active;
struct Capture {Callback callback;void* user;std::string failure;};
int callback(void* user,std::uint32_t event,const std::uint8_t* data,std::uint32_t size) {
    auto& captured=*static_cast<Capture*>(user);
    try {if(event==0)active->feed(data,size);return captured.callback(captured.user,event,data,size);}
    catch(const Failure& error){captured.failure=error.message;}
    catch(const std::exception& error){captured.failure=error.what();}
    catch(...){captured.failure="conditional_consumer_failure";}
    return -1;
}
template<class Action> int capture(Action action,std::uint32_t mode,Callback outer,void* user,std::uint64_t* receipt,char* error,std::uint32_t size) noexcept {
    try {
        need(active && !active->running && !active->attempted && !active->finished && mode<=1 && outer && receipt && error && size && size<=1024,"conditional_capture_configuration");
        Capture state{outer,user,{}};active->running=true;active->attempted=true;
        const auto code=action(callback,&state);active->running=false;
        if(!state.failure.empty()){error_text(error,size,state.failure.c_str());receipt[4]=0;return -2;}
        active->source_complete=code==0 && receipt[4]==1;return code;
    } catch(const Failure& failure){error_text(error,size,failure.message);}
    catch(...){error_text(error,size,"conditional_capture_failure");}
    if(active)active->running=false;
    if(receipt)receipt[4]=0;
    return -2;
}
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_conditional_census_abi() noexcept{return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_conditional_census_begin(const char* output,std::uint64_t bytes,std::uint64_t records) noexcept {
    try {if(conditional_census::active)return -1;conditional_census::active=std::make_unique<conditional_census::Census>(output,bytes,records);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_conditional_census_finish(std::uint64_t* out,std::uint32_t words,char* error,std::uint32_t size) noexcept {
    if(!out || words!=conditional_census::width || !error || !size || size>1024)return -1;
    std::fill(out,out+words,0);
    try {need(bool(conditional_census::active),"conditional_missing_census");conditional_census::active->finish();std::copy(conditional_census::active->counts.begin(),conditional_census::active->counts.end(),out);return 0;}
    catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"conditional_finish_failure");}return -2;
}
extern "C" __attribute__((visibility("default"))) void gp_conditional_census_release() noexcept {
    if(!conditional_census::active || !conditional_census::active->running)conditional_census::active.reset();
}
extern "C" __attribute__((visibility("default"))) int gp_conditional_census_frames(const std::uint8_t* data,std::uint64_t bytes,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept {
    if(!receipt || receipt_count!=receipt_size)return -1;
    return conditional_census::capture([&](Callback sink,void* state){return gp_country_screen_frames(data,bytes,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},mode,outer,user,receipt,error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_conditional_census_pbf(const char* path,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept {
    if(!receipt || receipt_count!=receipt_size)return -1;
    return conditional_census::capture([&](Callback sink,void* state){return gp_country_screen_pbf(path,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},mode,outer,user,receipt,error,size);
}
