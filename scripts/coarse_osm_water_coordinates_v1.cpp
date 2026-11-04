// Exact source E7 coordinates for a qualified sorted native-ID set.
#include "coarse_osm_topology_source_v1.cpp"

namespace water_coordinates {
constexpr std::size_t chunk=1048576;
constexpr std::uint64_t id_cap=150000000;
constexpr std::array<std::uint8_t,4> magic{{'W','X','Y','1'}};
class Ids {
public:
    std::vector<std::uint64_t> values;
    std::uint64_t expected;
    bool ready=false;
    explicit Ids(std::uint64_t count):expected(count){need(count<=id_cap,"water_xy_id_capacity");values.reserve(count);}
    void append(const std::uint64_t* data,std::uint32_t count){
        need(!ready && data && count && count<=131072 && values.size()+count<=expected,"water_xy_id_chunk");
        auto previous=values.empty()?0:values.back();
        for(std::uint32_t i=0;i<count;++i){need(data[i]>previous && data[i]<(std::uint64_t(1)<<63),"water_xy_id_order_domain");previous=data[i];}
        values.insert(values.end(),data,data+count);
    }
    void seal(){need(!ready && values.size()==expected,"water_xy_complete_id_input");ready=true;}
};
class Output {
    std::array<Bytes,3> buffers_;
public:
    std::array<std::uint64_t,3> bytes{};
    Callback sink=nullptr;void* user=nullptr;
    void flush(unsigned channel){
        auto& buffer=buffers_[channel];if(buffer.empty())return;
        need(sink && sink(user,30+channel,buffer.data(),buffer.size())==0,"water_xy_output_callback");buffer.clear();
    }
    void put(unsigned channel,const std::uint8_t* data,std::size_t size){
        bytes[channel]=checked_add(bytes[channel],size);
        auto& buffer=buffers_[channel];
        while(size){const auto n=std::min(size,chunk-buffer.size());buffer.insert(buffer.end(),data,data+n);
            data+=n;size-=n;if(buffer.size()==chunk)flush(channel);}
    }
    void integer(unsigned channel,std::uint64_t value,unsigned size){
        std::uint8_t data[8];for(unsigned i=0;i<size;++i)data[i]=static_cast<std::uint8_t>(value>>(8*i));put(channel,data,size);
    }
    void variable(std::uint64_t value){
        std::uint8_t data[10];unsigned n=0;
        while(value>=128){data[n++]=static_cast<std::uint8_t>((value&127)|128);value>>=7;}data[n++]=value;put(0,data,n);
    }
    void canonical(std::uint64_t identity,std::int64_t x,std::int64_t y){integer(2,identity,8);integer(2,static_cast<std::uint32_t>(x),4);integer(2,static_cast<std::uint32_t>(y),4);}
    void flush_all(){for(unsigned i=0;i<3;++i)flush(i);}
    void detach(){sink=nullptr;user=nullptr;}
};
std::uint64_t zigzag(std::int64_t value){return value>=0?2*value:-2*value-1;}
std::int64_t signed32(std::uint64_t value){return value<(std::uint64_t(1)<<31)?static_cast<std::int64_t>(value):static_cast<std::int64_t>(value)-(std::int64_t(1)<<32);}

class Capture {
    Bytes pending_;
    std::size_t cursor_=0;
    std::uint64_t previous_source_=0,previous_id_=0;
    std::int64_t previous_x_=0,previous_y_=0;
    void missing(){output.integer(1,ids.values[cursor_++],8);++absent;}
    void record(const std::uint8_t* body,std::uint32_t size){
        Input in{body,size};need(in.number(4)==0x31465047,"water_xy_frame_magic");
        const auto kind=in.number(1);need(kind<3,"water_xy_frame_kind");if(kind!=0)return;
        need(in.number(1)==1 && in.number(2)==0,"water_xy_frame_state");const auto identity=in.number(8);
        need(identity>previous_source_,"water_xy_source_node_order");previous_source_=identity;
        while(cursor_<ids.values.size() && ids.values[cursor_]<identity)missing();
        if(cursor_==ids.values.size() || ids.values[cursor_]!=identity)return;
        in.number(8);in.string();const auto tags=in.number(4);need(tags<=(size-in.position)/8,"water_xy_tag_count");
        for(std::uint64_t i=0;i<tags;++i){in.string();in.string();}
        const auto x=signed32(in.number(4)),y=signed32(in.number(4));
        need(in.position==in.size && x>=-1800000000 && x<=1800000000 && y>=-900000000 && y<=900000000,"water_xy_source_e7_fields");
        output.variable(identity-previous_id_);output.variable(zigzag(x-previous_x_));output.variable(zigzag(y-previous_y_));
        output.canonical(identity,x,y);previous_id_=identity;previous_x_=x;previous_y_=y;++cursor_;++present;
    }
public:
    Ids ids;Output output;
    std::uint64_t present=0,absent=0;
    bool running=false,attempted=false,complete=false,finished=false;
    explicit Capture(std::uint64_t count):ids(count){}
    void feed(const std::uint8_t* data,std::uint32_t size){
        need(size<=chunk && pending_.size()+size<=9437188,"water_xy_pending_cap");pending_.insert(pending_.end(),data,data+size);
        std::size_t cursor=0;
        while(pending_.size()-cursor>=4){Input length{pending_.data()+cursor,4};const auto n=length.number(4);
            need(n && n<=8388608,"water_xy_frame_cap");if(pending_.size()-cursor-4<n)break;record(pending_.data()+cursor+4,n);cursor+=4+n;}
        if(cursor)pending_.erase(pending_.begin(),pending_.begin()+cursor);
    }
    void end(bool success){
        if(success){need(pending_.empty(),"water_xy_pending_eof");while(cursor_<ids.values.size())missing();
            need(present+absent==ids.expected,"water_xy_source_partition");output.flush_all();}
        complete=success;output.detach();
    }
    std::array<std::uint64_t,8> finish(){
        need(!running && complete && !finished && output.bytes[1]==absent*8 && output.bytes[2]==present*16,"water_xy_complete_source_required");finished=true;
        return {{ids.expected,present,absent,output.bytes[0],output.bytes[2],output.bytes[1],1,0}};
    }
};
class Decoder {
    std::size_t cursor_=0;
    unsigned header_=0,shift_=0,field_=0;
    std::uint64_t value_=0,delta_id_=0,previous_id_=0,encoded_=0;
    std::int64_t delta_x_=0,x_=0,y_=0;
    void missing(){output.integer(1,ids.values[cursor_++],8);++absent;}
    void value(std::uint64_t number){
        if(field_==0){need(number && number<(std::uint64_t(1)<<63),"water_xy_decoded_id_delta");delta_id_=number;}
        else if(field_==1){need(number<=7200000000ULL,"water_xy_decoded_x_delta");delta_x_=number%2?-static_cast<std::int64_t>(number/2)-1:static_cast<std::int64_t>(number/2);}
        else{
            need(number<=3600000000ULL && previous_id_<(std::uint64_t(1)<<63)-delta_id_,"water_xy_decoded_y_delta_id_sum");
            const auto dy=number%2?-static_cast<std::int64_t>(number/2)-1:static_cast<std::int64_t>(number/2);
            const auto identity=previous_id_+delta_id_;const auto x=x_+delta_x_,y=y_+dy;
            need(x>=-1800000000 && x<=1800000000 && y>=-900000000 && y<=900000000,"water_xy_decoded_e7_range");
            while(cursor_<ids.values.size() && ids.values[cursor_]<identity)missing();
            need(cursor_<ids.values.size() && ids.values[cursor_]==identity,"water_xy_decoded_requested_id_partition");
            ++cursor_;++present;output.canonical(identity,x,y);previous_id_=identity;x_=x;y_=y;
        }
        field_=(field_+1)%3;
    }
public:
    Ids ids;Output output;std::uint64_t present=0,absent=0;
    bool running=false,finished=false,failed=false;
    explicit Decoder(std::uint64_t count):ids(count){}
    void feed(const std::uint8_t* data,std::uint32_t size){
        need(ids.ready && !finished && !failed && data && size && size<=chunk,"water_xy_decoder_state_chunk");encoded_=checked_add(encoded_,size);
        for(std::uint32_t i=0;i<size;++i){const auto byte=data[i];
            if(header_<magic.size()){need(byte==magic[header_++],"water_xy_codec_magic");continue;}
            need(shift_<64 && (shift_!=63 || byte<=1),"water_xy_varint_overflow");value_|=std::uint64_t(byte&127)<<shift_;
            if(byte&128){shift_+=7;continue;}
            need(!shift_ || byte,"water_xy_varint_canonical");value(value_);value_=0;shift_=0;
        }
    }
    std::array<std::uint64_t,8> finish(){
        need(ids.ready && !finished && !failed && header_==magic.size() && !field_ && !shift_,"water_xy_decoder_complete_eof");finished=true;
        while(cursor_<ids.values.size())missing();output.flush_all();
        need(present+absent==ids.expected && output.bytes[1]==absent*8 && output.bytes[2]==present*16,"water_xy_decoder_partition_counts");
        return {{ids.expected,present,absent,encoded_,output.bytes[2],output.bytes[1],1,0}};
    }
};
thread_local std::unique_ptr<Capture> active;
thread_local std::unique_ptr<Decoder> audit;
struct Forward{Callback callback;void* user;std::string failure;};
int callback(void* user,std::uint32_t event,const std::uint8_t* data,std::uint32_t size){
    auto& state=*static_cast<Forward*>(user);
    try{if(event==0)active->feed(data,size);return state.callback(state.user,event,data,size);}
    catch(const Failure& error){state.failure=error.message;}catch(const std::exception& error){state.failure=error.what();}catch(...){state.failure="water_xy_capture_callback_failure";}return -1;
}
template<class Action> int capture(Action action,Callback outer,void* user,std::uint64_t* receipt,char* error,std::uint32_t size) noexcept{
    try{need(active && active->ids.ready && !active->running && !active->attempted && !active->finished && outer && receipt && error && size && size<=1024,"water_xy_capture_configuration");
        Forward state{outer,user,{}};active->running=true;active->attempted=true;active->output.sink=outer;active->output.user=user;
        active->output.put(0,magic.data(),magic.size());const auto code=action(callback,&state);active->running=false;
        if(!state.failure.empty()){error_text(error,size,state.failure.c_str());receipt[4]=0;active->end(false);return -2;}
        active->end(code==0 && receipt[4]==1);return code;
    }catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_xy_capture_failure");}
    if(active){active->running=false;active->end(false);}if(receipt)receipt[4]=0;return -2;
}
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_water_coords_abi() noexcept{return 0x10000;}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_begin(std::uint64_t count) noexcept{
    try{if(water_coordinates::active || water_coordinates::audit)return -1;water_coordinates::active=std::make_unique<water_coordinates::Capture>(count);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_append(const std::uint64_t* ids,std::uint32_t count) noexcept{
    try{need(water_coordinates::active && !water_coordinates::active->attempted,"water_xy_input_session");water_coordinates::active->ids.append(ids,count);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_seal() noexcept{
    try{need(bool(water_coordinates::active),"water_xy_input_session");water_coordinates::active->ids.seal();return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_finish(std::uint64_t* out,std::uint32_t words,char* error,std::uint32_t size) noexcept{
    if(!out || words!=8 || !error || !size || size>1024)return -1;std::fill(out,out+words,0);
    try{need(bool(water_coordinates::active),"water_xy_missing_capture");auto counts=water_coordinates::active->finish();std::copy(counts.begin(),counts.end(),out);return 0;}
    catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_xy_finish_failure");}return -2;
}
extern "C" __attribute__((visibility("default"))) void gp_water_coords_release() noexcept{if(!water_coordinates::active || !water_coordinates::active->running)water_coordinates::active.reset();}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_frames(const std::uint8_t* data,std::uint64_t bytes,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept{
    if(!receipt || receipt_count!=receipt_size || mode>1)return -1;
    return water_coordinates::capture([&](Callback sink,void* state){return gp_country_screen_frames(data,bytes,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},outer,user,receipt,error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_pbf(const char* path,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,const std::int64_t* selected,std::uint32_t selected_count,Callback outer,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t size) noexcept{
    if(!receipt || receipt_count!=receipt_size || mode>1)return -1;
    return water_coordinates::capture([&](Callback sink,void* state){return gp_country_screen_pbf(path,snapshot,limit,limits,limits_count,mode,selected,selected_count,sink,state,receipt,receipt_count,error,size);},outer,user,receipt,error,size);
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_audit_begin(std::uint64_t count) noexcept{
    try{if(water_coordinates::active || water_coordinates::audit)return -1;water_coordinates::audit=std::make_unique<water_coordinates::Decoder>(count);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_audit_append(const std::uint64_t* ids,std::uint32_t count) noexcept{
    try{need(bool(water_coordinates::audit),"water_xy_audit_input_session");water_coordinates::audit->ids.append(ids,count);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_audit_seal() noexcept{
    try{need(bool(water_coordinates::audit),"water_xy_audit_input_session");water_coordinates::audit->ids.seal();return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_audit_feed(const std::uint8_t* data,std::uint32_t bytes,Callback sink,void* user,char* error,std::uint32_t size) noexcept{
    if(!sink || !error || !size || size>1024)return -1;
    try{need(water_coordinates::audit && !water_coordinates::audit->running,"water_xy_audit_feed_session");auto& state=*water_coordinates::audit;
        state.running=true;state.output.sink=sink;state.output.user=user;state.feed(data,bytes);state.output.detach();state.running=false;return 0;}
    catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_xy_audit_feed_failure");}
    if(water_coordinates::audit){water_coordinates::audit->failed=true;water_coordinates::audit->running=false;water_coordinates::audit->output.detach();}return -2;
}
extern "C" __attribute__((visibility("default"))) int gp_water_coords_audit_finish(std::uint64_t* out,std::uint32_t words,Callback sink,void* user,char* error,std::uint32_t size) noexcept{
    if(!out || words!=8 || !sink || !error || !size || size>1024)return -1;std::fill(out,out+words,0);
    try{need(water_coordinates::audit && !water_coordinates::audit->running,"water_xy_audit_finish_session");auto& state=*water_coordinates::audit;
        state.running=true;state.output.sink=sink;state.output.user=user;auto counts=state.finish();state.output.detach();state.running=false;std::copy(counts.begin(),counts.end(),out);return 0;}
    catch(const Failure& failure){error_text(error,size,failure.message);}catch(...){error_text(error,size,"water_xy_audit_finish_failure");}
    if(water_coordinates::audit){water_coordinates::audit->failed=true;water_coordinates::audit->running=false;water_coordinates::audit->output.detach();}return -2;
}
extern "C" __attribute__((visibility("default"))) void gp_water_coords_audit_release() noexcept{if(!water_coordinates::audit || !water_coordinates::audit->running)water_coordinates::audit.reset();}
