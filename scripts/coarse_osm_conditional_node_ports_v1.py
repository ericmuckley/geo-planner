"""Complete typed-source port qualification, independently replayed by binary lookup/join."""
from array import array
from bisect import bisect_left,bisect_right
import math

from coarse_osm_conditional_node_turns_v2 import KINDS
from coarse_timing_input import require

MAX_SELECTED_PORTS=1000000
MAX_RULE_PORTS=8192


def records(field):
    if hasattr(field,'parts'):
        for part in field.parts:
            for row in field.row.iter_unpack(part):yield row[0] if len(row)==1 else row
    else:yield from field


class WayIdentities:
    def __init__(self,ways):self.ways=ways
    def __len__(self):return len(self.ways)
    def __getitem__(self,index):return self.ways[index][0]


def validate_rules(rules):
    require(len(rules)<=100000,'Conditional port rule bound')
    previous=0
    for rule in rules:
        require(all(type(v) is int and 0<v<2**63 for v in (rule.identity,rule.from_way,rule.via_node,rule.to_way)),'Exact positive native rule IDs')
        require(previous<rule.identity and rule.from_way!=rule.to_way and rule.kind in KINDS,'Sorted unique supported source rules')
        previous=rule.identity


def way_columns(ways,wanted,check):
    found={};flags=array('H');points=array('I');previous=end=0
    require(flags.itemsize==2 and points.itemsize==4,'Fixed source column widths')
    for index,row in enumerate(records(ways)):
        if index%65536==0:check()
        identity,forward,backward,value,following=row
        require(type(identity) is int and previous<identity<2**63 and type(value) is int and 0<=value<2560,'All source way identities/flags')
        require(all(math.isfinite(v) and 0<=v<=160 for v in (forward,backward)) and bool(value&1)==(forward>0) and bool(value&2)==(backward>0),'All source direction/speed fields')
        require(bool(value>>8)!=bool(value&3) and type(following) is int and end<=following<2**32,'All source eligibility/geometry offsets')
        flags.append(value);points.append(following-end)
        if identity in wanted:found[identity]=index
        previous=identity;end=following
    require(len(flags)==len(ways),'Every source way row checked')
    return found,flags,points,end


def source_maps(fields,rules,check):
    ids,anchors=fields['ids'],fields['anchors']
    wanted_nodes={r.via_node for r in rules};wanted_ways={w for r in rules for w in (r.from_way,r.to_way)}
    anchor_values=array('I');previous=-1
    for index,value in enumerate(records(anchors)):
        if index%65536==0:check()
        require(type(value) is int and previous<value<len(ids),'All source anchors unique/sorted/in range')
        anchor_values.append(value);previous=value
    require(len(anchor_values)==len(anchors),'Complete source anchor table')
    nodes={};vertices={};previous=seen=0
    for index,identity in enumerate(records(ids)):
        if index%65536==0:check()
        require(type(identity) is int and previous<identity<2**63,'Complete sorted native source node IDs')
        if identity in wanted_nodes:
            nodes[identity]=index;at=bisect_left(anchor_values,index)
            if at<len(anchor_values) and anchor_values[at]==index:vertices[identity]=at
        previous=identity;seen+=1
    require(seen==len(ids),'Every source native node checked')
    ways,flags,points,end=way_columns(fields['ways'],wanted_ways,check)
    return nodes,vertices,ways,flags,points,end


def descriptor(rule,nodes,vertices,ways,flags):
    result={'sourceRelationId':str(rule.identity),'fromWayId':str(rule.from_way),'viaNodeId':str(rule.via_node),'toWayId':str(rule.to_way),'kind':rule.kind,
            'fromWayRow':ways.get(rule.from_way),'toWayRow':ways.get(rule.to_way),'viaSourceNodeIndex':nodes.get(rule.via_node),'viaAnchor':vertices.get(rule.via_node)}
    if rule.from_way not in ways:reason='from-way-outside-major-facts'
    elif rule.to_way not in ways:reason='to-way-outside-major-facts'
    elif not flags[ways[rule.from_way]]&3:reason='from-way-base-ineligible'
    elif not flags[ways[rule.to_way]]&3:reason='to-way-base-ineligible'
    elif rule.via_node not in nodes:reason='via-node-not-in-selected-source'
    elif rule.via_node not in vertices:reason='via-node-not-an-anchor'
    else:reason=None
    result['status']=reason
    return result


def arc_records(fields,flags,points,check):
    previous=None;seen=0
    for index,row in enumerate(records(fields['arcs'])):
        if index%65536==0:check()
        tail,head,way,first,last,direction,padding,ms=row
        require(all(type(v) is int for v in (tail,head,way,first,last,direction,ms)) and 0<=tail<len(fields['anchors']) and 0<=head<len(fields['anchors']) and 0<=way<len(flags),'Every source arc vertex/way domain')
        require(0<=first<last<points[way] and direction in (-1,1) and flags[way]&(1 if direction==1 else 2),'Every source arc geometry/direction')
        require(padding==bytes(3) and 0<ms<=0xffffffff*125,'Every source arc padding/cost')
        key=(way,first,last,-direction);require(previous is None or previous<key,'Complete pre-closure source arc order')
        previous=key;seen+=1
        yield index,tail,head,way
    require(seen==len(fields['arcs']),'Complete source pre-arc count')


def finish_descriptor(row,incoming,outgoing):
    result=row|{'incomingPreArcIds':incoming,'outgoingPreArcIds':outgoing}
    if row['status'] is not None:return result
    if not incoming:reason='no-directed-incoming-source-port'
    elif not outgoing:reason='no-directed-outgoing-source-port'
    elif max(len(incoming),len(outgoing))>MAX_RULE_PORTS or len(incoming)*len(outgoing)>MAX_SELECTED_PORTS:reason='source-port-complexity-fallback'
    else:reason='source-ports-supported'
    return result|{'status':reason}


def qualify(fields,rules,check=lambda:None):
    validate_rules(rules)
    require(set(fields)=={'ids','anchors','ways','arcs'} and 0<len(fields['anchors'])<=len(fields['ids'])<=64000000 and len(fields['anchors'])<=0xffffff and 0<len(fields['ways'])<=5000000 and len(fields['arcs'])<=0xffffff,'Complete bounded source dimensions')
    nodes,vertices,ways,flags,points,end=source_maps(fields,rules,check)
    descriptions=[descriptor(r,nodes,vertices,ways,flags) for r in rules]
    incoming={(r['fromWayRow'],r['viaAnchor']):[] for r in descriptions if r['status'] is None}
    outgoing={(r['toWayRow'],r['viaAnchor']):[] for r in descriptions if r['status'] is None}
    wanted={key[0] for key in incoming}|{key[0] for key in outgoing};selected=0
    for index,tail,head,way in arc_records(fields,flags,points,check):
        if way not in wanted:continue
        if (way,head) in incoming:incoming[way,head].append(index);selected+=1
        if (way,tail) in outgoing:outgoing[way,tail].append(index);selected+=1
        require(selected<=MAX_SELECTED_PORTS,'Selected complete source port cap')
    rows=[finish_descriptor(r,incoming.get((r['fromWayRow'],r['viaAnchor']),[]) if r['status'] is None else [],outgoing.get((r['toWayRow'],r['viaAnchor']),[]) if r['status'] is None else []) for r in descriptions]
    return {'rows':rows,'allSourceNodeIdsChecked':len(fields['ids']),'allSourceAnchorsChecked':len(fields['anchors']),
            'allSourceWayRowsChecked':len(fields['ways']),'allSourcePreArcsChecked':len(fields['arcs']),
            'sourceGeometryReferenceCount':end,'selectedSourcePortRows':selected}


def audit(fields,rules,actual,check=lambda:None):
    validate_rules(rules)
    for name,key in [('ids','allSourceNodeIdsChecked'),('anchors','allSourceAnchorsChecked'),('ways','allSourceWayRowsChecked'),('arcs','allSourcePreArcsChecked')]:
        require(actual[key]==len(fields[name]),'Complete independently checked source dimensions')
    # Independent native-ID binary searches replace the producer's streaming maps.
    identities=WayIdentities(fields['ways']);nodes={};vertices={};ways={}
    for index,rule in enumerate(rules):
        if index%256==0:check()
        at=bisect_left(fields['ids'],rule.via_node)
        if at<len(fields['ids']) and fields['ids'][at]==rule.via_node:
            nodes[rule.via_node]=at;vertex=bisect_left(fields['anchors'],at)
            if vertex<len(fields['anchors']) and fields['anchors'][vertex]==at:vertices[rule.via_node]=vertex
        for identity in (rule.from_way,rule.to_way):
            at=bisect_left(identities,identity)
            if at<len(identities) and identities[at]==identity:ways[identity]=at
    _,flags,points,end=way_columns(fields['ways'],set(ways),check)
    descriptions=[descriptor(r,nodes,vertices,ways,flags) for r in rules]
    keys=sorted({(r['fromWayRow'],r['viaAnchor'],0) for r in descriptions if r['status'] is None}|{(r['toWayRow'],r['viaAnchor'],1) for r in descriptions if r['status'] is None})
    wanted={key[0] for key in keys};joined=[]
    # Re-read every source arc and sort/merge selected incidence tuples.
    for index,tail,head,way in arc_records(fields,flags,points,check):
        if way not in wanted:continue
        for vertex,direction in ((head,0),(tail,1)):
            key=(way,vertex,direction);at=bisect_left(keys,key)
            if at<len(keys) and keys[at]==key:
                joined.append((*key,index));require(len(joined)<=MAX_SELECTED_PORTS,'Independent port tuple cap')
    joined.sort()
    def ports(way,vertex,direction):
        return [row[3] for row in joined[bisect_left(joined,(way,vertex,direction,0)):bisect_right(joined,(way,vertex,direction,0xffffff))]]
    expected=[finish_descriptor(r,ports(r['fromWayRow'],r['viaAnchor'],0) if r['status'] is None else [],ports(r['toWayRow'],r['viaAnchor'],1) if r['status'] is None else []) for r in descriptions]
    require(actual['rows']==expected and actual['sourceGeometryReferenceCount']==end,'Every source ID/anchor/directed-port descriptor independently replays')
    require(actual['selectedSourcePortRows']==len(joined),'Every selected source incidence counted independently')
    return {'allCandidateSourceDescriptorsIndependentlyReplayed':len(expected),
            'secondSourcePreArcsChecked':len(fields['arcs']),'independentSelectedSourcePortRows':len(joined),
            'supportedRules':sum(r['status']=='source-ports-supported' for r in expected),
            'sourceOrGraphChanged':False}
