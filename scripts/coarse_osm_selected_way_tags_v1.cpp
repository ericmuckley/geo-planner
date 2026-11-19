// Select complete original way tags through the immutable whole-source validator.
// Selection is an arbitrary sorted ID set; source decisions and geometry never change.
#include "coarse_osm_topology_source_v1.cpp"
#include <fcntl.h>
#include <unistd.h>

namespace selected_way_tags {
constexpr unsigned width = 16;
constexpr std::uint64_t output_limit = 48ULL*1048576, record_limit = 250000;
class Census {
    Bytes pending_;
    int output_ = -1;
    std::uint64_t outputLimit_;
    std::vector<std::uint64_t> selected_;
    std::size_t cursor_ = 0;
    void append(const Bytes& body) {
        need(counts[3]<selected_.size() && body.size()<=8388608 && body.size()+4<=outputLimit_-counts[5],"node_tags_output_cap");
        Bytes encoded;put32(encoded,static_cast<std::uint32_t>(body.size()));encoded.insert(encoded.end(),body.begin(),body.end());
        std::size_t at=0;
        while(at<encoded.size()) {const auto n=::write(output_,encoded.data()+at,encoded.size()-at);need(n>0,"node_tags_output_write");at+=n;}
        add(3);add(5,encoded.size());counts[6]=std::max(counts[6],static_cast<std::uint64_t>(encoded.size()));
    }
    void changed(std::uint8_t kind,std::uint64_t identity,const std::vector<std::pair<std::string,std::string>>& tags) {
        Bytes body{'C','S','T','1',kind,0,0,0};put64(body,identity);put32(body,static_cast<std::uint32_t>(tags.size()));
        for(const auto& item:tags) {text(body,item.first);text(body,item.second);add(4,item.first.size()+item.second.size());}
        append(body);counts[7]=identity;
    }
    void record(const std::uint8_t* body,std::uint32_t size) {
        Input in{body,size};need(in.number(4)==0x31465047,"node_tags_frame_magic");
        const auto kind=in.number(1);need(kind<3,"node_tags_frame_kind");add(kind);
        if(kind!=1)return; // Every object is already checked by the sealed source validator.
        need(in.number(1)==1 && in.number(2)==0,"node_tags_frame_state");
        const auto identity=in.number(8);
        need(cursor_==selected_.size() || selected_[cursor_]>=identity,"node_tags_missing_selected");
        if(cursor_==selected_.size() || selected_[cursor_]!=identity)return;
        in.number(8);in.string();const auto n=in.number(4);
        need(n<=(size-in.position)/8,"node_tags_tag_count");
        std::vector<std::pair<std::string,std::string>> tags;
        for(std::uint64_t i=0;i<n;++i) {
            const auto key=in.string(),value=in.string();
            tags.emplace_back(key,value);
        }
        changed(1,identity,tags);++cursor_;
    }


public:
    std::array<std::uint64_t,width> counts{};
    bool running=false, attempted=false, source_complete=false, finished=false;
    explicit Census(const std::uint64_t* selected,std::uint32_t count,const char* output,std::uint64_t bytes):outputLimit_(bytes) {
        need(count<=record_limit && (!count || selected),"node_tags_selection_bound");
        for(std::uint32_t i=0;i<count;++i) {
            need(selected[i]>0 && selected[i]<0x8000000000000000ULL && (!i || selected[i]>selected[i-1]),"node_tags_selection_order");
            selected_.push_back(selected[i]);
        }
        counts[8]=count;
        need(bytes>0 && bytes<=output_limit,"node_tags_output_limits");
        need(output && strnlen(output,4097)<=4096,"node_tags_output_path");
        output_=::open(output,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);need(output_>=0,"node_tags_fresh_output");
    }
    ~Census() {if(output_>=0)::close(output_);}
    void add(unsigned at,std::uint64_t n=1) {counts[at]=checked_add(counts[at],n);}
    void feed(const std::uint8_t* data,std::uint32_t size) {
        need(!finished && size<=1048576 && pending_.size()+size<=9437188,"node_tags_semantic_buffer_cap");
        pending_.insert(pending_.end(),data,data+size);
        std::size_t cursor=0;
        while(pending_.size()-cursor>=4) {
            Input length{pending_.data()+cursor,4};const auto n=length.number(4);
            need(n && n<=8388608,"node_tags_semantic_frame_cap");
            if(pending_.size()-cursor-4<n)break;
            record(pending_.data()+cursor+4,static_cast<std::uint32_t>(n));cursor+=4+n;
        }
        if(cursor)pending_.erase(pending_.begin(),pending_.begin()+cursor);
    }
    void finish() {
        need(!running && source_complete && !finished && pending_.empty() && cursor_==selected_.size(),"node_tags_complete_source_required");
        struct stat state{};need(::fstat(output_,&state)==0 && S_ISREG(state.st_mode) && state.st_nlink==1 && static_cast<std::uint64_t>(state.st_size)==counts[5],"node_tags_output_stat");
        const int descriptor=output_;output_=-1;need(::close(descriptor)==0,"node_tags_output_close");
        counts[9]=1;finished=true;
    }
};
thread_local std::unique_ptr<Census> active;
struct Capture {Callback callback;void* user;std::string failure;};
int callback(void* user,std::uint32_t event,const std::uint8_t* data,std::uint32_t size) {
    auto& captured=*static_cast<Capture*>(user);
    try {if(event==0)active->feed(data,size);return captured.callback(captured.user,event,data,size);}
    catch(const Failure& error){captured.failure=error.message;}
    catch(const std::exception& error){captured.failure=error.what();}
    catch(...){captured.failure="node_tags_consumer_failure";}
    return -1;
}
template<class Action> int capture(Action action,std::uint32_t mode,Callback outer,void* user,std::uint64_t* receipt,char* error,std::uint32_t size) noexcept {
    try {
        need(active && !active->running && !active->attempted && !active->finished && mode<=1 && outer && receipt && error && size && size<=1024,"node_tags_capture_configuration");
        Capture state{outer,user,{}};active->running=true;active->attempted=true;
        const auto code=action(callback,&state);active->running=false;
        if(!state.failure.empty()){error_text(error,size,state.failure.c_str());receipt[4]=0;return -2;}
        active->source_complete=code==0 && receipt[4]==1;return code;
    } catch(const Failure& failure){error_text(error,size,failure.message);}
    catch(...){error_text(error,size,"node_tags_capture_failure");}
    if(active)active->running=false;
    if(receipt)receipt[4]=0;
    return -2;
}
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_selected_way_tags_abi() noexcept{return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_selected_way_tags_begin(const std::uint64_t* selected,std::uint32_t count,const char* output,std::uint64_t bytes) noexcept {
    try {if(selected_way_tags::active)return -1;selected_way_tags::active=std::make_unique<selected_way_tags::Census>(selected,count,output,bytes);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_selected_way_tags_finish(std::uint64_t* out,std::uint32_t words,char* error,std::uint32_t size) noexcept {
    if(!out || words!=selected_way_tags::width || !error || !size || size>1024)return -1;
    std::fill(out,out+words,0);
    try {need(bool(selected_way_tags::active),"node_tags_missing_census");selected_way_tags::active->finish();std::copy(selected_way_tags::active->counts.begin(),selected_way_tags::active->counts.end(),out);return 0;}
    catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"node_tags_finish_failure");}return -2;
}
extern "C" __attribute__((visibility("default"))) void gp_selected_way_tags_release() noexcept {
    if(!selected_way_tags::active || !selected_way_tags::active->running)selected_way_tags::active.reset();
}
extern "C" __attribute__((visibility("default"))) int gp_selected_way_tags_frames(const std::uint8_t* data,std::uint64_t bytes,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept {
    if(!receipt || receipt_count!=receipt_size)return -1;
    return selected_way_tags::capture([&](Callback sink,void* state){return gp_country_screen_frames(data,bytes,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},mode,outer,user,receipt,error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_selected_way_tags_pbf(const char* path,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept {
    if(!receipt || receipt_count!=receipt_size)return -1;
    return selected_way_tags::capture([&](Callback sink,void* state){return gp_country_screen_pbf(path,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},mode,outer,user,receipt,error,size);
}
