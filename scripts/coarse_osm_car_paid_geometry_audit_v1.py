"""Independent all-source paid packet/prefix/length audit; no native producer.

National columns are typed arrays, with only one small source span expanded at
a time. Projection uses an independent spherical local-basis calculation.
"""
from array import array
from bisect import bisect_left
import math
from pathlib import Path
import struct
import time

from coarse_osm_car_packed_audit_v1 import rows,unpack24
from coarse_osm_paid_projection_v1 import frame,project
from import_roads import distance_m

FILES={'curve-keys.u24','curve-offsets.u32','curve-packets.u8','long-keys.u24','long-lengths.u16',
       'long-overflow-keys.u24','long-overflow-units.u32','curve-source.bin','curve-source-positions.u32','long-source.bin'}
ARC=struct.Struct('<IIIIIb3sQ');PROVENANCE=struct.Struct('<IIIb3s');MAX_MS=(2**32-1)*125


def varint(raw,cursor,end):
    value=0
    for i in range(5):
        assert cursor<end
        byte=raw[cursor];cursor+=1;value|=(byte&127)<<(7*i)
        if byte<128:
            assert value<=0xffffffff and (i==0 or byte!=0)
            return value,cursor
    raise AssertionError('Geometry varint exceeds uint32')


def curve_packet(raw,first,last,start_xy):
    x,y=start_xy;cursor=first;out=[]
    while cursor<last:
        a,cursor=varint(raw,cursor,last);b,cursor=varint(raw,cursor,last)
        x=(x+((a>>1)^-(a&1)))&0xffffffff;y=(y+((b>>1)^-(b&1)))&0xffffffff
        x=x-2**32 if x>=2**31 else x;y=y-2**32 if y>=2**31 else y
        assert -1800000000<=x<=1800000000 and -900000000<=y<=900000000 and cursor+4<=last
        f,b=struct.unpack_from('<HH',raw,cursor);cursor+=4;out.append((x,y,f,b))
        assert len(out)<=1048576
    assert cursor==last
    return out


def fraction(prefix,total):return 0 if total==0 else (prefix*65535+total//2)//total


def audit(source,offset_path,map_path,output,expected,check=lambda:None):
    began=time.monotonic();source=Path(source);output=Path(output)
    nodes,vertices,way_count,refs,pre_expected,post=expected
    assert 0<nodes<=64000000 and 0<vertices<=0xffffff and 0<way_count<=8000000 and refs<=64000000 and post<=pre_expected<=0xffffff
    assert {path.name for path in output.iterdir()}==FILES
    def read(root,name):
        path=root/name;assert path.is_file() and not path.is_symlink() and path.stat().st_size<=67108864
        return path.read_bytes()
    def words(root,name,code):
        out=array(code);out.frombytes(read(root,name));return out
    def column(prefix,code,width,maximum):
        out=array(code)
        for path in sorted(source.glob(prefix+'-*.bin')):
            assert path.is_file() and not path.is_symlink() and path.stat().st_size<=16777216 and path.stat().st_size%width==0
            assert len(out)*out.itemsize+path.stat().st_size<=maximum*width
            out.frombytes(path.read_bytes())
        return out
    xy=column('xy','i',8,nodes);geometry=column('geometry','I',4,refs);anchors=column('anchors','I',4,vertices)
    assert len(xy)==2*nodes and len(geometry)==refs and len(anchors)==vertices
    assert all(-1800000000<=xy[i]<=1800000000 and -900000000<=xy[i+1]<=900000000 for i in range(0,len(xy),2))
    assert all(node<nodes for node in geometry) and all(a<b for a,b in zip(anchors,anchors[1:])) and anchors[-1]<nodes
    ids=array('Q');ends=array('I');speeds_f=array('d');speeds_b=array('d')
    for identity,f,b,flags,end in rows(source,'ways',struct.Struct('<QddII')):
        assert len(ids)<way_count
        assert identity>0 and (not ids or identity>ids[-1]) and (not ends or end>=ends[-1]) and end<=refs
        assert math.isfinite(f) and math.isfinite(b) and 0<=f<=160 and 0<=b<=160 and bool(flags&1)==(f>0) and bool(flags&2)==(b>0)
        ids.append(identity);ends.append(end);speeds_f.append(f);speeds_b.append(b)
    assert len(ids)==way_count and ends[-1]==refs
    blocked=bytearray(way_count);previous_closed=0
    for identity, in rows(source,'closures',struct.Struct('<Q')):
        assert identity>previous_closed;previous_closed=identity;at=bisect_left(ids,identity)
        if at<way_count and ids[at]==identity:blocked[at]=1
    for path,size in ((Path(offset_path),3*(vertices+1)),(Path(map_path),4*post)):
        assert path.is_file() and not path.is_symlink() and path.stat().st_size==size<=67108864
    offsets=unpack24(Path(offset_path).read_bytes());arc_map=array('I');arc_map.frombytes(Path(map_path).read_bytes())
    assert len(offsets)==vertices+1 and offsets[0]==0 and offsets[-1]==post and len(arc_map)==post and all(a<=b for a,b in zip(offsets,offsets[1:]))
    seen=bytearray((post+7)//8)
    for arc in arc_map:
        assert arc<post and not seen[arc>>3]&(1<<(arc&7));seen[arc>>3]|=1<<(arc&7)
    del seen
    cursor=array('I',offsets[:-1]);keys=unpack24(read(output,'curve-keys.u24'));starts=words(output,'curve-offsets.u32','I');packets=read(output,'curve-packets.u8')
    positions=words(output,'curve-source-positions.u32','I');provenance=read(output,'curve-source.bin')
    long_keys=unpack24(read(output,'long-keys.u24'));lengths=words(output,'long-lengths.u16','H');long_provenance=read(output,'long-source.bin')
    overflow_keys=unpack24(read(output,'long-overflow-keys.u24'));overflow_values=words(output,'long-overflow-units.u32','I')
    for values in (keys,long_keys,overflow_keys):assert all(a<b for a,b in zip(values,values[1:])) and (not values or values[-1]<post)
    assert len(starts)==len(keys)+1 and starts[0]==0 and starts[-1]==len(packets) and all(a<b for a,b in zip(starts,starts[1:]))
    assert len(provenance)==16*len(keys) and len(long_provenance)==16*len(long_keys) and len(long_keys)==len(lengths)
    assert len(overflow_keys)==len(overflow_values)==sum(value==65535 for value in lengths) and all(value>=65535 for value in overflow_values)
    curve_rows=array('i',[-1])*post;long_rows=array('i',[-1])*post
    for i,key in enumerate(keys):curve_rows[key]=i
    for i,key in enumerate(long_keys):long_rows[key]=i
    point_starts=array('I',[0])
    for i in range(len(keys)):
        position=starts[i];count=0
        while position<starts[i+1]:
            _,position=varint(packets,position,starts[i+1]);_,position=varint(packets,position,starts[i+1]);position+=4;count+=1
        assert position==starts[i+1] and 0<count<=1048576;point_starts.append(point_starts[-1]+count)
    assert point_starts[-1]==len(positions)
    curve_seen=bytearray(len(keys));long_seen=bytearray(len(long_keys))
    pre=active=physical=interiors=0;prior=None;pending=None;max_geo=max_time=max_length=0.
    def coordinate(node):return xy[2*node],xy[2*node+1]
    for tail,head,way,first,last,direction,padding,milliseconds in rows(source,'arcs',ARC):
        pre+=1;assert pre<=pre_expected and tail<vertices and head<vertices and way<way_count and first<last and last-first<1048576 and direction in (-1,1) and padding==b'\0'*3 and 0<milliseconds<=MAX_MS
        begin=ends[way-1] if way else 0
        assert last<ends[way]-begin and geometry[begin+first]==anchors[tail if direction==1 else head] and geometry[begin+last]==anchors[head if direction==1 else tail]
        key=(way,first,last);duplicate=prior is not None and key==prior[0]
        assert prior is None or key>prior[0] or duplicate and prior[1]==1 and direction==-1
        if not duplicate:assert pending is None
        prior=key,direction
        if blocked[way]:continue
        active+=1;csr=cursor[tail];cursor[tail]+=1;assert csr<offsets[tail+1]
        if duplicate:
            assert pending==(csr,milliseconds);pending=None;continue
        physical+=1;assert (speeds_f[way] if direction==1 else speeds_b[way])>0
        canonical=arc_map[csr];canonical_direction=direction;both=speeds_f[way]>0 and speeds_b[way]>0
        other=cursor[head] if both else None
        if both:
            assert direction==1 and other<offsets[head+1]
            if arc_map[other]<canonical:canonical=arc_map[other];canonical_direction=-direction
        cr=curve_rows[canonical];lr=long_rows[canonical]
        source_positions=[];decoded=[]
        if cr>=0:
            assert not curve_seen[cr];curve_seen[cr]=1
            assert PROVENANCE.unpack_from(provenance,16*cr)==(way,first,last,canonical_direction,b'\0'*3)
            source_positions=list(positions[point_starts[cr]:point_starts[cr+1]])
            assert all(first<p<last for p in source_positions) and all((b-a)*canonical_direction>0 for a,b in zip(source_positions,source_positions[1:]))
            start_node=geometry[begin+(first if canonical_direction==1 else last)]
            decoded=curve_packet(packets,starts[cr],starts[cr+1],coordinate(start_node))
            assert len(decoded)==len(source_positions)
            for point,pos in zip(decoded,source_positions):assert point[:2]==coordinate(geometry[begin+pos])
        kept=[first]+(source_positions if canonical_direction==1 else source_positions[::-1])+[last]
        f=array('Q',[0]);b=array('Q',[0]);length=0.
        for i in range(first+1,last+1):
            a_node=geometry[begin+i-1];b_node=geometry[begin+i];a=coordinate(a_node);q=coordinate(b_node)
            distance=distance_m([v/1e7 for v in a],[v/1e7 for v in q]);length+=distance
            f.append(f[-1]+(0 if a_node==b_node or not speeds_f[way] else max(1,math.ceil(distance*3600/speeds_f[way]))))
            b.append(b[-1]+(0 if a_node==b_node or not speeds_b[way] else max(1,math.ceil(distance*3600/speeds_b[way]))))
        assert f[-1]<=MAX_MS and b[-1]<=MAX_MS and milliseconds==(f[-1] if direction==1 else b[-1])
        if both:pending=other,b[-1]
        for point,pos in zip(decoded,source_positions):
            i=pos-first
            expected_f=fraction(f[i],f[-1]) if canonical_direction==1 else fraction(b[-1]-b[i],b[-1])
            expected_b=fraction(b[i],b[-1]) if canonical_direction==1 else fraction(f[-1]-f[i],f[-1])
            assert point[2:]==(expected_f,expected_b)
        for a_pos,b_pos in zip(kept,kept[1:]):
            segment=frame(coordinate(geometry[begin+a_pos]),coordinate(geometry[begin+b_pos]))
            for i in range(a_pos+1,b_pos):
                distance,ratio=project(coordinate(geometry[begin+i]),segment)
                ef=abs((f[i-first]-f[a_pos-first])-ratio*(f[b_pos-first]-f[a_pos-first]))
                eb=abs((b[i-first]-b[a_pos-first])-ratio*(b[b_pos-first]-b[a_pos-first]))
                error=max(ef,eb);max_geo=max(max_geo,distance);max_time=max(max_time,error)
                # Separate numerical allowances: 1 mm in position, 1 ms in the
                # independent spherical calculation of an interval's time.
                assert distance<=100.001 and error<=10001,(canonical,distance,error)
        interiors+=len(source_positions);max_length=max(max_length,length)
        assert (lr>=0)==(length>1000) or abs(length-1000)<.001
        if lr>=0:
            assert not long_seen[lr];long_seen[lr]=1
            assert PROVENANCE.unpack_from(long_provenance,16*lr)==(way,first,last,canonical_direction,b'\0'*3)
            units=lengths[lr]
            if units==65535:
                at=bisect_left(overflow_keys,canonical);assert at<len(overflow_keys) and overflow_keys[at]==canonical;units=overflow_values[at]
            assert 8-.001<=8*units-length<=16+.001
        if physical%100000==0:check()
    assert pre==pre_expected and active==post and pending is None and cursor==array('I',offsets[1:])
    assert all(curve_seen) and all(long_seen) and interiors==len(positions)
    runtime=sum((output/name).stat().st_size for name in FILES if name not in ('curve-source.bin','curve-source-positions.u32','long-source.bin'))
    return {'status':'independent_complete_paid_geometry_source_packet_prefix_length_audit_passed',
            'physicalSpansChecked':physical,'directedSourceCostsChecked':active,'curvedSpansChecked':len(keys),'interiorPositionsChecked':interiors,
            'longSpansChecked':len(long_keys),'lengthOverflowsChecked':len(overflow_keys),'runtimeBytes':runtime,
            'maximumDiscardedSourcePointErrorMeters':max_geo,'maximumDiscardedSourceTimeErrorMs':max_time,
            'maximumFullSpanMeters':max_length,'secondsIndependentSourceAudit':time.monotonic()-began,
            'sourcePbfReads':0,'nativeProducerExecutions':0,'originSnapOrEtaOrAppQualified':False}
