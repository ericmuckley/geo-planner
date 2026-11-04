"""Independent full packed-output audit from closed typed facts.

No native formatter, source decoder, producer, policy helper or graph query.
Uses dense typed arrays and two source-arc passes; no national node dictionary.
"""
from array import array
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
import struct
import time

FILES = {'xy.i32','offsets.u24','targets.u24','costs.u16','cost-overflow-arcs.u24',
         'cost-overflow-ticks.u32','reverse.u8','reverse-overflow-arcs.u24',
         'reverse-overflow-targets.u24','node-flags.u8','forbidden-turns.u24'}
ARC = struct.Struct('<IIIIIb3sQ')


def rows(root, prefix, shape):
    for path in sorted(Path(root).glob(prefix+'-*.bin')):
        assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216
        with path.open('rb') as stream:
            while raw := stream.read(shape.size*16384):
                assert len(raw)%shape.size == 0
                yield from shape.iter_unpack(raw)


def unpack24(raw):
    assert len(raw)%3 == 0
    return array('I',(raw[i] | raw[i+1]<<8 | raw[i+2]<<16 for i in range(0,len(raw),3)))


def audit(source, routing, expected):
    began = time.monotonic();source = Path(source);routing = Path(routing)
    nodes, vertices, ways_count, pre_count, count, turn_count = expected
    assert 0 < nodes <= 64000000 and 0 < vertices <= 0xffffff and count <= pre_count <= 0xffffff
    assert {path.name for path in routing.iterdir()} == FILES
    def read(name):
        path = routing/name
        assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 67108864
        return path.read_bytes()
    def words(name, code):
        out = array(code);out.frombytes(read(name));return out
    offsets = unpack24(read('offsets.u24'));targets = unpack24(read('targets.u24'))
    costs = words('costs.u16','H');cost_keys = unpack24(read('cost-overflow-arcs.u24'));cost_values = words('cost-overflow-ticks.u32','I')
    reverse = read('reverse.u8');reverse_keys = unpack24(read('reverse-overflow-arcs.u24'));reverse_values = unpack24(read('reverse-overflow-targets.u24'))
    flags = read('node-flags.u8');xy = words('xy.i32','i');forbidden = unpack24(read('forbidden-turns.u24'))
    assert len(offsets) == vertices+1 and offsets[0] == 0 and offsets[-1] == count
    assert all(a<=b for a,b in zip(offsets,offsets[1:]))
    assert len(targets) == len(costs) == len(reverse) == count and all(head<vertices for head in targets)
    assert len(flags) == vertices and all(flag<8 for flag in flags) and len(xy) == 2*vertices
    def keys_valid(keys, values):
        assert len(keys)==len(values) and all(a<b for a,b in zip(keys,keys[1:])) and (not keys or keys[-1]<count)
    keys_valid(cost_keys,cost_values);keys_valid(reverse_keys,reverse_values)
    assert len(cost_keys) == sum(value==65535 for value in costs)
    assert all(costs[key]==65535 and value>=65535 for key,value in zip(cost_keys,cost_values))
    assert len(reverse_keys) == reverse.count(254)
    assert all(reverse[key]==254 and value<count for key,value in zip(reverse_keys,reverse_values))
    assert len(forbidden)%2 == 0
    assert all(value<count for value in forbidden)
    assert all((forbidden[i],forbidden[i+1])<(forbidden[i+2],forbidden[i+3]) for i in range(0,len(forbidden)-2,2))
    def overflow(keys, values, arc):
        position = bisect_left(keys,arc);assert position<len(keys) and keys[position]==arc
        return values[position]
    def reverse_at(arc):
        value = reverse[arc]
        if value==255:return None
        other = overflow(reverse_keys,reverse_values,arc) if value==254 else offsets[targets[arc]]+value
        assert offsets[targets[arc]] <= other < offsets[targets[arc]+1]
        if value==254:assert other-offsets[targets[arc]]>=254
        return other
    anchors = array('I',(node for node, in rows(source,'anchors',struct.Struct('<I'))))
    assert len(anchors)==vertices and anchors[-1]<nodes and all(a<b for a,b in zip(anchors,anchors[1:]))
    identities = array('Q');cursor = seen = 0
    for ordinal,(identity,) in enumerate(rows(source,'ids',struct.Struct('<Q'))):
        seen += 1
        if cursor<vertices and ordinal==anchors[cursor]:identities.append(identity);cursor += 1
    assert seen==nodes and cursor==vertices and all(a<b for a,b in zip(identities,identities[1:]))
    cursor = seen = 0
    for ordinal,(x,y) in enumerate(rows(source,'xy',struct.Struct('<ii'))):
        seen += 1
        if cursor<vertices and ordinal==anchors[cursor]:
            assert xy[2*cursor]==x and xy[2*cursor+1]==y;cursor += 1
    assert seen==nodes and cursor==vertices
    assert flags == bytes(flag for flag, in rows(source,'flags',struct.Struct('<B')))
    ways = array('Q',(row[0] for row in rows(source,'ways',struct.Struct('<QddII'))))
    assert len(ways)==ways_count and all(a<b for a,b in zip(ways,ways[1:]))
    closed = bytearray(ways_count)
    for identity, in rows(source,'closures',struct.Struct('<Q')):
        position = bisect_left(ways,identity)
        if position<ways_count and ways[position]==identity:closed[position]=1
    degree = array('I',[0])*vertices;pre = retained = 0
    for tail,head,way,first,last,direction,padding,ms in rows(source,'arcs',ARC):
        pre += 1
        assert tail<vertices and head<vertices and way<ways_count and first<last and direction in (-1,1) and padding==b'\0'*3 and 0<ms<=0xffffffff*125
        if not closed[way]:degree[tail]+=1;retained += 1
    assert (pre,retained)==(pre_count,count)
    assert all(offsets[i+1]-offsets[i]==degree[i] for i in range(vertices))
    del degree
    cursor = array('I',offsets[:-1]);arc_ways = array('I',[0])*count;pending = None;checked = 0
    for tail,head,way,first,last,direction,_,ms in rows(source,'arcs',ARC):
        if closed[way]:continue
        index = cursor[tail];cursor[tail] += 1
        assert index<offsets[tail+1] and targets[index]==head
        actual = overflow(cost_keys,cost_values,index) if costs[index]==65535 else costs[index]
        assert actual==(ms+124)//125
        arc_ways[index]=way;checked += 1
        key = (way,first,last)
        if pending is not None and pending[0]==key:
            _,other,old_tail,old_head,old_direction = pending
            assert old_direction==1 and direction==-1 and old_tail==head and old_head==tail
            assert reverse_at(other)==index and reverse_at(index)==other;pending=None
        else:
            if pending is not None:assert reverse_at(pending[1]) is None
            pending=(key,index,tail,head,direction)
    if pending is not None:assert reverse_at(pending[1]) is None
    assert checked==count and cursor==array('I',offsets[1:])
    rules = defaultdict(list);turns = relevant = 0
    for _,source_way,via,target_way,kind,padding in rows(source,'turns',struct.Struct('<QQQQB7s')):
        turns += 1;assert kind<10 and padding==b'\0'*7
        a = bisect_left(ways,source_way);b = bisect_left(identities,via)
        if a<ways_count and ways[a]==source_way and b<vertices and identities[b]==via:
            rules[a,b].append((target_way,kind));relevant += 1
    assert turns==turn_count
    position = 0
    for incoming in range(count):
        source_way = ways[arc_ways[incoming]];head = targets[incoming]
        current = rules.get((arc_ways[incoming],head))
        if not current:continue
        physical_reverse = reverse_at(incoming)
        for outgoing in range(offsets[head],offsets[head+1]):
            target_way = ways[arc_ways[outgoing]];only = [];blocked = False
            for to,kind in current:
                match = target_way==to
                if source_way==to:match = match and ((outgoing==physical_reverse) if kind in (3,9) else (outgoing!=physical_reverse))
                if kind>=6:only.append(match)
                elif match:blocked=True
            if blocked or only and not any(only):
                assert position+1<len(forbidden) and forbidden[position]==incoming and forbidden[position+1]==outgoing
                position += 2
    assert position==len(forbidden)
    return {'status':'independent_complete_packed_routing_audit_passed','verticesChecked':vertices,
            'directedCostsAndPhysicalReversesChecked':checked,'sourceTurnRecordsChecked':turns,
            'relevantSourceTurnRecords':relevant,'forbiddenTurnPairsChecked':position//2,
            'costOverflowEntries':len(cost_keys),'reverseOverflowEntries':len(reverse_keys),
            'secondsIndependentDerivedAudit':time.monotonic()-began,'sourcePbfReads':0,
            'nativeLibraryExecutions':0,'sourceConstructorExecutions':0,'etaQualified':False,'vercelQualified':False}
