"""Small independent permutation oracle. Refuses national-sized Python objects."""
from array import array
import struct

from coarse_osm_packed_capture_v1 import pack24


def morton(x,y):
    assert -1800000000<=x<=1800000000 and -900000000<=y<=900000000
    x+=1800000000;y+=900000000;key=0
    for bit in range(32):key|=((x>>bit)&1)<<(2*bit);key|=((y>>bit)&1)<<(2*bit+1)
    return key


def unpack24(raw):
    assert len(raw)%3==0
    return [int.from_bytes(raw[i:i+3],'little') for i in range(0,len(raw),3)]


def permute(fields):
    assert sum(map(len,fields.values()))<=16*1048576
    def words(name,code):
        out=array(code);out.frombytes(fields[name]);return out
    flags=fields['node-flags.u8'];vertices=len(flags);assert 0<vertices<=200000
    offsets=unpack24(fields['offsets.u24']);targets=unpack24(fields['targets.u24']);arcs=len(targets);assert arcs<=200000
    xy=words('xy.i32','i');costs=words('costs.u16','H');reverse=fields['reverse.u8']
    order=sorted(range(vertices),key=lambda old:(morton(*xy[2*old:2*old+2]),old))
    vertex_map={old:new for new,old in enumerate(order)};arc_order=[];new_offsets=[0]
    for old in order:arc_order.extend(range(offsets[old],offsets[old+1]));new_offsets.append(len(arc_order))
    arc_map={old:new for new,old in enumerate(arc_order)}
    def overflow(prefix,value_name,arc_values):
        keys=unpack24(fields[prefix+'-overflow-arcs.u24'])
        values=unpack24(fields[value_name]) if arc_values else words(value_name,'I')
        return sorted((arc_map[a],arc_map[b] if arc_values else b) for a,b in zip(keys,values))
    cost_overflow=overflow('cost','cost-overflow-ticks.u32',False);reverse_overflow=overflow('reverse','reverse-overflow-targets.u24',True)
    old_pairs=unpack24(fields['forbidden-turns.u24']);pairs=sorted((arc_map[a],arc_map[b]) for a,b in zip(old_pairs[::2],old_pairs[1::2]))
    cells=[];starts=[]
    for new,old in enumerate(order):
        cell=morton(*xy[2*old:2*old+2])>>40
        if not cells or cell!=cells[-1]:cells.append(cell);starts.append(new)
    starts.append(vertices)
    return {'xy.i32':array('i',(value for old in order for value in xy[2*old:2*old+2])).tobytes(),
            'offsets.u24':pack24(new_offsets),'targets.u24':pack24(vertex_map[targets[old]] for old in arc_order),
            'costs.u16':array('H',(costs[old] for old in arc_order)).tobytes(),
            'cost-overflow-arcs.u24':pack24(a for a,b in cost_overflow),'cost-overflow-ticks.u32':array('I',(b for a,b in cost_overflow)).tobytes(),
            'reverse.u8':bytes(reverse[old] for old in arc_order),'reverse-overflow-arcs.u24':pack24(a for a,b in reverse_overflow),
            'reverse-overflow-targets.u24':pack24(b for a,b in reverse_overflow),'node-flags.u8':bytes(flags[old] for old in order),
            'forbidden-turns.u24':pack24(v for pair in pairs for v in pair),'cell-keys.u24':pack24(cells),'cell-offsets.u24':pack24(starts),
            'new-vertex-to-old.u32':array('I',order).tobytes(),'old-arc-to-new.u32':array('I',(arc_map[i] for i in range(arcs))).tobytes()}


def fixture():
    return {'xy.i32':struct.pack('<8i',-1000000000,350000000,-800000000,400000000,-1200000000,320000000,-1000000000,350000000),
            'offsets.u24':pack24([0,2,3,4,6]),'targets.u24':pack24([1,3,0,3,0,2]),'costs.u16':struct.pack('<6H',1,65535,2,3,4,5),
            'cost-overflow-arcs.u24':pack24([1]),'cost-overflow-ticks.u32':struct.pack('<I',70000),
            'reverse.u8':bytes([0,0,0,1,1,0]),'reverse-overflow-arcs.u24':b'','reverse-overflow-targets.u24':b'',
            'node-flags.u8':bytes([4,6,1,4]),'forbidden-turns.u24':pack24([0,2,1,5])}
