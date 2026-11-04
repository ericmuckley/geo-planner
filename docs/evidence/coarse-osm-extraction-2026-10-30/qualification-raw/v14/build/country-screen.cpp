// Complete-extraction V6 prototype: complete per-type summaries, retaining the frozen V1 guards.
// Source-validation copy/canonical limit is 4 MiB, sized from the complete relation census.
// The predecessor cannot be refactored after its evidence was sealed.
// File hashes/framing and SHA256 remain in the Python bridge.
#include <algorithm>
#include <array>
#include <cfenv>
#include <cstdint>
#include <cstring>
#include <exception>
#include <limits>
#include <chrono>
#include <tuple>
#include <sys/stat.h>
#include <osmium/thread/pool.hpp>
#include <string>
#include <string_view>
#include <vector>
#include <osmium/handler.hpp>
#include <osmium/io/pbf_input.hpp>
#include <osmium/visitor.hpp>

extern "C" int gp_delta_encode(const std::int64_t*, const std::int32_t*, std::uint32_t,
                               std::uint8_t*, std::uint32_t, std::uint32_t*) noexcept;
extern "C" int gp_delta_decode(const std::uint8_t*, std::uint32_t, std::uint32_t,
                               std::int64_t, std::int64_t, std::int64_t*, std::int32_t*, std::uint32_t) noexcept;
namespace {
using Bytes = std::vector<std::uint8_t>;
using View = std::string_view;
using Callback = int (*)(void*, std::uint32_t, const std::uint8_t*, std::uint32_t);
constexpr std::uint32_t max_element = 4194304, max_frame = 8388608, batch_bytes = 1048576;
constexpr std::uint64_t max_visits = 1770542426, max_input = 16777216;
constexpr std::uint64_t source_bytes = 12229320016ULL;
constexpr unsigned receipt_size = 56, limits_size = 12;
constexpr std::uint32_t block_rows = 4096, max_payload = 69623;
struct Failure { const char* message; };
void need(bool condition, const char* message) { if (!condition) throw Failure{message}; }
void put32(Bytes& out, std::uint32_t value) {
    for (unsigned k = 0; k != 4; ++k) out.push_back(static_cast<std::uint8_t>(value >> (8*k)));
}
void put64(Bytes& out, std::uint64_t value) {
    for (unsigned k = 0; k != 8; ++k) out.push_back(static_cast<std::uint8_t>(value >> (8*k)));
}
void text(Bytes& out, View value) {
    need(value.size() <= max_frame, "string_bound"); put32(out, static_cast<std::uint32_t>(value.size()));
    out.insert(out.end(), value.begin(), value.end());
}
struct Input {
    const std::uint8_t* data; std::size_t size, position = 0;
    std::uint64_t number(unsigned width) {
        need(width <= size-position, "truncated_frame"); std::uint64_t value=0;
        for (unsigned k=0; k!=width; ++k) value |= std::uint64_t(data[position++]) << (8*k);
        return value;
    }
    std::int64_t signed64() {
        const auto n=number(8);
        return n <= 0x7fffffffffffffffULL ? static_cast<std::int64_t>(n) : -1-static_cast<std::int64_t>(~n);
    }
    std::int32_t signed32() {
        const auto n=number(4);return n <= 0x7fffffffULL ? static_cast<std::int32_t>(n) : static_cast<std::int32_t>(static_cast<std::int64_t>(n)-0x100000000LL);
    }
    View string() {
        const auto n=number(4);need(n<=max_frame && n<=size-position,"string_frame_bound");
        const View result(reinterpret_cast<const char*>(data+position),static_cast<std::size_t>(n));position+=n;return result;
    }
};
// Exact Python ensure_ascii string length, validating only Unicode scalar UTF-8.
std::uint64_t escaped(View value) {
    std::uint64_t count=2;
    for (std::size_t p=0;p<value.size();) {
        const auto lead=static_cast<unsigned char>(value[p++]);std::uint32_t cp=lead;unsigned trailing=0;
        if (lead>=0x80) {
            if (lead>=0xc2 && lead<=0xdf) { cp=lead&31;trailing=1; }
            else if (lead>=0xe0 && lead<=0xef) { cp=lead&15;trailing=2; }
            else if (lead>=0xf0 && lead<=0xf4) { cp=lead&7;trailing=3; }
            else throw Failure{"invalid_utf8"};
            need(trailing<=value.size()-p,"truncated_utf8");
            for (unsigned k=0;k<trailing;++k) {
                const auto next=static_cast<unsigned char>(value[p++]);need((next&0xc0)==0x80,"invalid_utf8");cp=(cp<<6)|(next&63);
            }
            need((trailing!=1 || cp>=0x80) && (trailing!=2 || cp>=0x800) && (trailing!=3 || cp>=0x10000)
                && cp<=0x10ffff && !(cp>=0xd800 && cp<=0xdfff),"invalid_utf8_scalar");
        }
        if (cp=='"' || cp=='\\' || cp==8 || cp==9 || cp==10 || cp==12 || cp==13) count+=2;
        else if (cp<32 || cp>=127) count+=cp<=0xffff ? 6 : 12;
        else ++count;
    }
    return count;
}
void timestamp(View s) {
    need(s.size()==20 && s[4]=='-' && s[7]=='-' && s[10]=='T' && s[13]==':' && s[16]==':' && s[19]=='Z',"timestamp_shape");
    for (unsigned p: {0,1,2,3,5,6,8,9,11,12,14,15,17,18}) need(s[p]>='0' && s[p]<='9',"timestamp_digits");
    const auto pair=[&](unsigned p){return (s[p]-'0')*10+s[p+1]-'0';};
    const int year=pair(0)*100+pair(2),month=pair(5),day=pair(8);
    need(year>=1 && month>=1 && month<=12 && pair(11)<=23 && pair(14)<=59 && pair(17)<=59,"timestamp_calendar");
    const std::array<int,12> days{{31,28,31,30,31,30,31,31,30,31,30,31}};
    const bool leap=year%4==0 && (year%100!=0 || year%400==0);
    need(day>=1 && day<=days[month-1]+(month==2 && leap),"timestamp_calendar");
}
std::uint64_t digits(std::int64_t n) { need(n>0,"positive_integer"); std::uint64_t size=1;while(n>=10){n/=10;++size;}return size; }
struct Member { std::uint8_t kind;std::int64_t ref;View role; };
struct Record {
    std::uint8_t kind=0,visible=0;std::int64_t id=0,version=0;View stamp;
    std::vector<std::pair<View,View>> tags;std::vector<std::int64_t> refs;std::vector<Member> members;
    std::int32_t x=0,y=0;std::uint64_t charge=256,tag_size=2;
};
View kind_name(std::uint8_t kind) { need(kind<3,"object_type");return kind==0 ? View("node") : kind==1 ? View("way") : View("relation"); }
Bytes frame(const Record& r) {
    Bytes out;out.reserve(static_cast<std::size_t>(r.charge));
    out.insert(out.end(),{'G','P','F','1',r.kind,r.visible,0,0});put64(out,static_cast<std::uint64_t>(r.id));put64(out,static_cast<std::uint64_t>(r.version));text(out,r.stamp);
    put32(out,static_cast<std::uint32_t>(r.tags.size()));
    for (const auto& tag:r.tags){text(out,tag.first);text(out,tag.second);}
    if (r.kind==0){put32(out,static_cast<std::uint32_t>(r.x));put32(out,static_cast<std::uint32_t>(r.y));}
    else if (r.kind==1){put32(out,static_cast<std::uint32_t>(r.refs.size()));for(auto ref:r.refs)put64(out,static_cast<std::uint64_t>(ref));}
    else {put32(out,static_cast<std::uint32_t>(r.members.size()));for(const auto& m:r.members){out.push_back(m.kind);put64(out,static_cast<std::uint64_t>(m.ref));text(out,m.role);}}
    need(out.size()<=max_frame,"projected_frame_bound");return out;
}
std::uint64_t field(View key,std::uint64_t value_size) { return escaped(key)+1+value_size; }
std::uint64_t canonical_without_node_floats(const Record& r) {
    const auto common=field("id",digits(r.id))+field("version",digits(r.version))+field("timestamp",22)+field("visible",4)+field("tags",r.tag_size)+field("type",escaped(kind_name(r.kind)));
    if (r.kind==0) return 2+7+common+field("lat",0)+field("lon",0);
    std::uint64_t value=2;
    if (r.kind==1) {
        for (auto ref:r.refs)value+=digits(ref);
        if (!r.refs.empty())value+=r.refs.size()-1;
        return 2+6+common+field("nodes",value);
    }
    for(const auto& m:r.members)value+=2+2+field("ref",digits(m.ref))+field("role",escaped(m.role))+field("type",escaped(kind_name(m.kind)));
    if (!r.members.empty())value+=r.members.size()-1;
    return 2+6+common+field("members",value);
}
std::uint64_t checked_add(std::uint64_t left,std::uint64_t right) {
    need(right<=std::numeric_limits<std::uint64_t>::max()-left,"counter_overflow");return left+right;
}
std::uint64_t priority(std::uint64_t identity) {
    auto x=(identity^0x47504c414e4e4552ULL)+0x9e3779b97f4a7c15ULL;
    x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);
}
std::uint64_t stratum(std::uint64_t shards,std::uint64_t k) {
    need(shards>0 && shards<=766 && k<8,"stratum_options");return k*(shards-1)/7;
}
struct Metadata {
    std::string first,last;
    std::array<std::uint64_t,6> maxima{};
};
struct Trace {
    std::uint64_t rank,id,ordinal,version;std::vector<std::int64_t> refs;
    auto key() const {return std::make_tuple(rank,id,ordinal);}
    bool operator<(const Trace& other) const {return key()<other.key();}
};
class Context {
    View snapshot_;std::uint32_t limit_,mode_;const std::int64_t* selected_;std::uint32_t selected_count_,cursor_=0;
    Callback callback_;void* user_;std::uint64_t* receipt_;std::array<std::uint64_t,limits_size> limits_;
    int last_kind_=-1;std::int64_t last_id_=0;Bytes semantic_,witness_;
    std::vector<std::int64_t> ids_;std::vector<std::int32_t> xy_;
    std::vector<std::uint64_t> selected_shards_;
    std::vector<std::pair<std::int64_t,std::int64_t>> ranges_;
    std::vector<Trace> trace_;std::tuple<std::uint64_t,std::uint64_t,std::uint64_t> next_{};
    bool has_next_=false;std::array<Metadata,3> metadata_;
    Bytes way_batch_;std::uint32_t batch_ways_=0,batch_refs_=0;
    const std::chrono::steady_clock::time_point began_=std::chrono::steady_clock::now();
    std::uint64_t elapsed() const {return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-began_).count();}
    void bump(unsigned index,std::uint64_t value=1) {receipt_[index]=checked_add(receipt_[index],value);}
    void excluded(const Trace& row) {if(!has_next_ || row.key()<next_){has_next_=true;next_=row.key();}}
    void semantic(const Bytes& encoded) {
        Bytes length;put32(length,static_cast<std::uint32_t>(encoded.size()));
        for(const Bytes* part:std::array<const Bytes*,2>{&length,&encoded}) {
            std::size_t position=0;
            while(position<part->size()) {
                const auto n=std::min<std::size_t>(batch_bytes-semantic_.size(),part->size()-position);
                semantic_.insert(semantic_.end(),part->begin()+position,part->begin()+position+n);position+=n;
                if(semantic_.size()==batch_bytes)flush_semantic();
            }
        }
    }
public:
    Context(const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t mode,
            const std::int64_t* selected,std::uint32_t count,Callback callback,void* user,std::uint64_t* receipt):
        snapshot_(snapshot ? View(snapshot,strnlen(snapshot,21)) : View{}),limit_(limit),mode_(mode),selected_(selected),selected_count_(count),callback_(callback),user_(user),receipt_(receipt) {
        need(callback && limits && limit>0 && limit<=max_element && mode<=3 && count<=2000000 && (!count || selected),"invalid_options");timestamp(snapshot_);
        for(unsigned k=0;k<limits_size;++k){limits_[k]=limits[k];need(limits[k]>0,"invalid_limit");}
        const std::array<std::uint64_t,4> maxima{{1606229364,162688797,1624265,max_visits}};
        for(unsigned k=0;k<4;++k)need(limits[k]<=maxima[k],"invalid_visit_limit");
        need(limits[4]<=source_bytes && limits[5]<=65536 && limits[6]<=5330986500096ULL && limits[7]<=13305978880ULL
            && limits[8]<=3713103671940456ULL && limits[9]<=3212458728ULL && limits[10]<=2000000 && limits[11]==65536,"invalid_screen_limit");
        for(std::uint32_t k=0;k<count;++k)need(selected[k]>0 && (!k || selected[k]>selected[k-1]),"selected_id_order");
        need(std::fegetround()==FE_TONEAREST && std::numeric_limits<double>::is_iec559,"floating_environment");
        const auto shards=(limits[0]+block_rows*512ULL-1)/(block_rows*512ULL);
        for(unsigned k=0;k<8;++k){const auto shard=stratum(shards,k);if(selected_shards_.empty() || selected_shards_.back()!=shard)selected_shards_.push_back(shard);}
        ids_.reserve(block_rows);xy_.reserve(block_rows*2);semantic_.reserve(batch_bytes);witness_.reserve(block_rows*16);trace_.reserve(128);
    }
    ~Context(){if(last_kind_>=0)receipt_[44+2*last_kind_]=elapsed();}
    void emit(std::uint32_t event,const Bytes& body) {need(body.size()<=max_frame,"callback_bound");need(callback_(user_,event,body.empty()?nullptr:body.data(),static_cast<std::uint32_t>(body.size()))==0,"callback_refused");}
    void begin(Record& r) {
        need(r.kind<3,"object_type");bump(r.kind);bump(3);
        need(receipt_[r.kind]<=limits_[r.kind] && receipt_[3]<=limits_[3],"native_visit_limit");
        need(r.id>0 && r.version>0 && (int(r.kind)>last_kind_ || (int(r.kind)==last_kind_ && r.id>last_id_)),"identity_order_version");
        // Restrictions must see every preceding way, including a partial batch.
        if(r.kind==2 && last_kind_==1)flush_way_batch();
        if(int(r.kind)!=last_kind_){const auto now=elapsed();if(last_kind_>=0)receipt_[44+2*last_kind_]=now;receipt_[43+2*r.kind]=now;}
        last_kind_=r.kind;last_id_=r.id;timestamp(r.stamp);need(r.stamp<=snapshot_ && r.visible==1,"snapshot_visibility");
    }
    void tag(Record& r,View key,View value) {
        r.charge+=key.size()+value.size()+64;need(r.charge<=limit_,"tag_copy_limit");
        r.tag_size+=escaped(key)+1+escaped(value)+(r.tags.empty()?0:1);r.tags.emplace_back(key,value);
    }
    void ref(Record& r,std::int64_t id) {bump(16);need(receipt_[16]<=limits_[6],"reference_total_limit");r.charge+=32;need(r.charge<=limit_ && id>0,"reference_copy_identity");r.refs.push_back(id);}
    void member(Record& r,std::uint8_t kind,std::int64_t id,View role) {
        bump(17);need(receipt_[17]<=limits_[7],"member_total_limit");
        r.charge+=role.size()+128;need(r.charge<=limit_ && kind<3 && id>0,"member_copy_identity");escaped(role);r.members.push_back({kind,id,role});bump(50+kind);
    }
    void flush_semantic() {if(!semantic_.empty()){bump(7,semantic_.size());need(receipt_[7]<=limits_[8],"semantic_total_limit");emit(0,semantic_);semantic_.clear();}}
    void flush_witness() {if(!witness_.empty()){emit(6,witness_);witness_.clear();}}
    void flush_nodes() {
        if(ids_.empty())return;
        const auto count=static_cast<std::uint32_t>(ids_.size());
        bump(27,count);need(checked_add(receipt_[27],receipt_[28])<=limits_[9],"codec_rows_limit");bump(29);need(receipt_[29]<=limits_[10],"codec_calls_limit");
        Bytes payload(max_payload);std::uint32_t written=0;
        need(gp_delta_encode(ids_.data(),xy_.data(),count,payload.data(),max_payload,&written)==0,"delta_encode_failure");payload.resize(written);
        std::array<std::int64_t,block_rows> ids{};std::array<std::int32_t,2*block_rows> xy{};
        bump(28,count);need(checked_add(receipt_[27],receipt_[28])<=limits_[9],"codec_rows_limit");bump(29);need(receipt_[29]<=limits_[10],"codec_calls_limit");
        need(gp_delta_decode(payload.data(),written,count,ids_.front(),ids_.back(),ids.data(),xy.data(),block_rows)==0
            && std::equal(ids_.begin(),ids_.end(),ids.begin()) && std::equal(xy_.begin(),xy_.end(),xy.begin()),"delta_source_roundtrip");
        const auto block=receipt_[6],shard=block/512;
        if(std::binary_search(selected_shards_.begin(),selected_shards_.end(),shard)) {
            if(block%512==0)ranges_.emplace_back(ids_.front(),ids_.back());else {need(!ranges_.empty(),"range_state");ranges_.back().second=ids_.back();}
        }
        Bytes out;out.reserve(24+written);put32(out,count);put64(out,ids_.front());put64(out,ids_.back());put32(out,written);out.insert(out.end(),payload.begin(),payload.end());
        emit(3,out);bump(6);ids_.clear();xy_.clear();
    }
    void checkpoint(){Bytes empty;bump(9);emit(4,empty);}
    void flush_way_batch() {
        if(!batch_ways_)return;
        Bytes body;body.reserve(16+way_batch_.size());body.insert(body.end(),{'G','W','B','1'});
        put32(body,batch_ways_);put32(body,batch_refs_);put32(body,way_batch_.size());body.insert(body.end(),way_batch_.begin(),way_batch_.end());
        bump(55);emit(8,body);way_batch_.clear();batch_ways_=batch_refs_=0;
    }
    void queue_way(const Bytes& encoded,std::uint32_t refs) {
        need(refs>=2 && refs<=65536 && encoded.size()+20<=max_frame,"way_batch_single_bound");
        if(batch_ways_==32768 || batch_refs_+refs>65536 || 20+way_batch_.size()+encoded.size()>max_frame)flush_way_batch();
        put32(way_batch_,encoded.size());way_batch_.insert(way_batch_.end(),encoded.begin(),encoded.end());
        ++batch_ways_;batch_refs_+=refs;bump(53);bump(54,refs);
    }
    void way_trace(const Record& r,const Bytes& encoded) {
        const auto tag=std::lower_bound(r.tags.begin(),r.tags.end(),View("highway"),[](const auto& t,View key){return t.first<key;});
        if(tag==r.tags.end() || tag->first!="highway")return;bump(30);
        if(mode_==3)queue_way(encoded,static_cast<std::uint32_t>(r.refs.size()));
        if(r.refs.size()>1024){bump(31);return;}
        bool inside=true;
        for(auto id:r.refs){bump(39);bool hit=false;for(const auto& range:ranges_)hit|=range.first<=id && id<=range.second;inside&=hit;}
        if(!inside){bump(32);return;}bump(33);
        if(mode_==2)queue_way(encoded,static_cast<std::uint32_t>(r.refs.size()));
        Trace candidate{priority(r.id),static_cast<std::uint64_t>(r.id),receipt_[1]-1,static_cast<std::uint64_t>(r.version),{}};
        if(trace_.size()==128 && !(candidate<trace_.front())){excluded(candidate);return;}
        candidate.refs=r.refs;
        if(trace_.size()==128){std::pop_heap(trace_.begin(),trace_.end());excluded(trace_.back());trace_.pop_back();}
        trace_.push_back(std::move(candidate));std::push_heap(trace_.begin(),trace_.end());
    }
    void consume(Record& r) {
        std::sort(r.tags.begin(),r.tags.end(),[](const auto& a,const auto& b){return a.first<b.first;});
        for(std::size_t k=1;k<r.tags.size();++k)need(r.tags[k-1].first!=r.tags[k].first,"duplicate_tag_key");
        if(r.kind==0)need(r.x>=-1800000000 && r.x<=1800000000 && r.y>=-900000000 && r.y<=900000000,"coordinate_range");
        if(r.kind==1)need(r.refs.size()>=2,"short_way");
        const auto size=canonical_without_node_floats(r);const auto lower=size+(r.kind==0?6:0),upper=size+(r.kind==0?64:0);
        bool fallback=false;
        if(r.kind==0){need(lower<=limit_,"canonical_byte_limit");fallback=upper>limit_;}else need(size<=limit_,"canonical_byte_limit");
        const Bytes encoded=frame(r);
        if(fallback){bump(5);need(receipt_[5]<=limits_[5],"fallback_total_limit");emit(1,encoded);}
        semantic(encoded);
        bool selected_node=false;
        if(r.kind==0){
            need(cursor_==selected_count_ || selected_[cursor_]>=r.id,"missing_witness");
            if(cursor_<selected_count_ && selected_[cursor_]==r.id){selected_node=true;put64(witness_,r.id);put32(witness_,r.x);put32(witness_,r.y);++cursor_;bump(36);if(witness_.size()==block_rows*16)flush_witness();}
            ids_.push_back(r.id);xy_.push_back(r.x);xy_.push_back(r.y);if(ids_.size()==block_rows)flush_nodes();
        }else{flush_nodes();if(r.kind==1)way_trace(r,encoded);}
        const bool restriction=r.kind==2 && std::any_of(r.tags.begin(),r.tags.end(),[](const auto& tag){return tag.first=="type" && tag.second=="restriction";});
        if(mode_==1 || (mode_==3 && (selected_node || restriction))){emit(2,encoded);bump(8);}
        bump(10+r.kind);receipt_[13+r.kind]=r.id;bump(18,lower);bump(19,upper);bump(20,r.charge);
        receipt_[21]=std::max(receipt_[21],r.charge);bump(22,r.tags.size());
        std::uint64_t tag_bytes=0;
        for(const auto& tag:r.tags){const auto n=tag.first.size()+tag.second.size();bump(23,n);tag_bytes=checked_add(tag_bytes,n);}
        auto& metadata=metadata_[r.kind];
        if(metadata.first.empty() || r.stamp<metadata.first)metadata.first.assign(r.stamp.data(),r.stamp.size());
        if(metadata.last.empty() || r.stamp>metadata.last)metadata.last.assign(r.stamp.data(),r.stamp.size());
        const std::array<std::uint64_t,6> sizes{{tag_bytes,r.tags.size(),static_cast<std::uint64_t>(r.version),r.charge,r.refs.size(),r.members.size()}};
        for(unsigned k=0;k<sizes.size();++k)metadata.maxima[k]=std::max(metadata.maxima[k],sizes[k]);
        receipt_[24]=std::max(receipt_[24],lower);receipt_[25]=std::max(receipt_[25],upper);receipt_[26]=std::max(receipt_[26],static_cast<std::uint64_t>(r.version));
        receipt_[37]=std::max<std::uint64_t>(receipt_[37],r.refs.size());receipt_[38]=std::max<std::uint64_t>(receipt_[38],r.members.size());receipt_[49]=std::max<std::uint64_t>(receipt_[49],r.tags.size());
        if(receipt_[3]%limits_[11]==0)checkpoint();
    }
    void finish(){
        flush_nodes();flush_semantic();flush_witness();flush_way_batch();need(cursor_==selected_count_,"missing_witness");
        std::sort(trace_.begin(),trace_.end());
        for(const auto& row:trace_){Bytes body;put64(body,row.id);put64(body,row.version);put64(body,row.ordinal);put64(body,row.rank);put32(body,row.refs.size());for(auto ref:row.refs)put64(body,ref);emit(5,body);bump(34);bump(35,row.refs.size());}
        if(has_next_){receipt_[40]=std::get<0>(next_);receipt_[41]=std::get<1>(next_);receipt_[42]=std::get<2>(next_);}
        for(unsigned kind=0;kind<3;++kind)if(receipt_[10+kind]){
            const auto& metadata=metadata_[kind];Bytes body;put32(body,kind);put64(body,receipt_[10+kind]);
            for(auto value:metadata.maxima)put64(body,value);
            body.insert(body.end(),metadata.first.begin(),metadata.first.end());body.insert(body.end(),metadata.last.begin(),metadata.last.end());
            need(body.size()==100,"metadata_summary_shape");emit(7,body);
        }
        checkpoint();receipt_[4]=1;
    }
};
void projected_frame(Input& in,Context& context) {
    need(in.number(4)==0x31465047,"frame_magic");Record r;r.kind=static_cast<std::uint8_t>(in.number(1));r.visible=static_cast<std::uint8_t>(in.number(1));need(in.number(2)==0,"frame_reserved");
    r.id=in.signed64();r.version=in.signed64();r.stamp=in.string();context.begin(r);
    const auto tags=in.number(4);need(tags<=(in.size-in.position)/8,"frame_tag_count");
    for(std::uint64_t k=0;k<tags;++k){const auto key=in.string();const auto value=in.string();context.tag(r,key,value);}
    if(r.kind==0){r.x=in.signed32();r.y=in.signed32();}
    else if(r.kind==1){const auto n=in.number(4);need(n<=(in.size-in.position)/8,"frame_reference_count");for(std::uint64_t k=0;k<n;++k)context.ref(r,in.signed64());}
    else {const auto n=in.number(4);need(n<=(in.size-in.position)/13,"frame_member_count");for(std::uint64_t k=0;k<n;++k){const auto kind=static_cast<std::uint8_t>(in.number(1));const auto ref=in.signed64();const auto role=in.string();context.member(r,kind,ref,role);}}
    need(in.position==in.size,"frame_trailing_bytes");context.consume(r);
}
View native_string(const char* p) {const auto n=strnlen(p,max_element+1);need(n<=max_element,"native_string_bound");return {p,n};}
struct Handler : osmium::handler::Handler {
    Context& context;explicit Handler(Context& c):context(c){}
    template<class Object> Record header(const Object& object,std::uint8_t kind,std::string& stamp) {
        // to_iso_all deliberately preserves epoch0; Timestamp::operator bool does not.
        stamp=object.timestamp().to_iso_all();Record r;r.kind=kind;r.id=object.id();r.version=object.version();r.visible=object.visible()?1:0;r.stamp=stamp;context.begin(r);
        for(const auto& tag:object.tags())context.tag(r,native_string(tag.key()),native_string(tag.value()));return r;
    }
    void node(const osmium::Node& object) {std::string stamp;auto r=header(object,0,stamp);r.x=object.location().x();r.y=object.location().y();context.consume(r);}
    void way(const osmium::Way& object) {std::string stamp;auto r=header(object,1,stamp);for(const auto& n:object.nodes())context.ref(r,n.ref());context.consume(r);}
    void relation(const osmium::Relation& object) {
        std::string stamp;auto r=header(object,2,stamp);
        for(const auto& m:object.members()){
            std::uint8_t kind=3;
            if(m.type()==osmium::item_type::node)kind=0;else if(m.type()==osmium::item_type::way)kind=1;else if(m.type()==osmium::item_type::relation)kind=2;
            context.member(r,kind,m.ref(),native_string(m.role()));
        }
        context.consume(r);
    }
};
void error_text(char* out,std::uint32_t capacity,const char* text) noexcept {
    if(!out || !capacity)return;const auto n=std::min<std::size_t>(capacity-1,std::strlen(text));std::memcpy(out,text,n);out[n]='\0';
}
template<class Action> int run(Action action,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,
        const std::int64_t* selected,std::uint32_t selected_count,Callback callback,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t error_size) noexcept {
    if(!receipt || receipt_count!=receipt_size || !error || !error_size || error_size>1024)return -1;
    std::fill(receipt,receipt+receipt_size,0);error[0]='\0';
    if(!limits || limits_count!=limits_size){error_text(error,error_size,"limits_array_length");return -1;}
    try {Context context(snapshot,limit,limits,mode,selected,selected_count,callback,user,receipt);action(context);context.finish();return 0;}
    catch(const Failure& e){error_text(error,error_size,e.message);}
    catch(const std::exception&){error_text(error,error_size,"decoder_or_allocation_failure");}
    catch(...){error_text(error,error_size,"unknown_native_failure");}
    receipt[4]=0;return -2;
}
}
extern "C" __attribute__((visibility("default"))) std::uint32_t gp_country_screen_abi() noexcept {return 0x60000;}
extern "C" __attribute__((visibility("default")))
int gp_country_screen_frames(const std::uint8_t* data,std::uint64_t size,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,
        const std::int64_t* selected,std::uint32_t selected_count,Callback callback,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t error_size) noexcept {
    return run([&](Context& c){need(size<=max_input && (!size || data),"frame_input_bound");Input input{data,static_cast<std::size_t>(size)};
        while(input.position<input.size){const auto n=input.number(4);need(n<=max_frame && n<=input.size-input.position,"frame_length");Input item{input.data+input.position,static_cast<std::size_t>(n)};projected_frame(item,c);input.position+=n;}},
        snapshot,limit,limits,limits_count,mode,selected,selected_count,callback,user,receipt,receipt_count,error,error_size);
}
extern "C" __attribute__((visibility("default")))
int gp_country_screen_pbf(const char* path,const char* snapshot,std::uint32_t limit,const std::uint64_t* limits,std::uint32_t limits_count,std::uint32_t mode,
        const std::int64_t* selected,std::uint32_t selected_count,Callback callback,void* user,std::uint64_t* receipt,std::uint32_t receipt_count,char* error,std::uint32_t error_size) noexcept {
    return run([&](Context& c){need(path && strnlen(path,4097)<=4096,"source_path_bound");struct stat state{};need(::stat(path,&state)==0 && state.st_size>=0 && static_cast<std::uint64_t>(state.st_size)<=limits[4],"source_file_bound");
        osmium::thread::Pool pool(2,2);osmium::io::Reader reader{path,osmium::osm_entity_bits::all,osmium::io::read_meta::yes,pool};Handler handler(c);osmium::apply(reader,handler);reader.close();},
        snapshot,limit,limits,limits_count,mode,selected,selected_count,callback,user,receipt,receipt_count,error,error_size);
}

// Small arithmetic exports exercise real checked operations without fake source receipts.
extern "C" __attribute__((visibility("default")))
int gp_country_screen_add(std::uint64_t a,std::uint64_t b,std::uint64_t* out) noexcept {
    if(!out)return -1;try{*out=checked_add(a,b);return 0;}catch(...){return -2;}
}
extern "C" __attribute__((visibility("default")))
std::uint64_t gp_country_screen_priority(std::uint64_t id) noexcept {return priority(id);}

extern "C" __attribute__((visibility("default")))
std::uint64_t gp_country_screen_stratum(std::uint64_t shards,std::uint64_t k) noexcept {
    try{return stratum(shards,k);}catch(...){return std::numeric_limits<std::uint64_t>::max();}
}
