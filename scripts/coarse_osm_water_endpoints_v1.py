"""Bounded way-endpoint facts and conservative relation-chain diagnostics."""
from array import array
from bisect import bisect_left
import struct

from coarse_osm_country_wire_v4 import FRAME_HEAD,decode_frame
from coarse_osm_water_ring_topology_v1 import join_degree_two
from coarse_timing_input import require

ROW=struct.Struct('<QQQIB3x')


def frames(reader):
    while prefix:=reader.read(4):
        require(len(prefix)==4,'Water endpoint complete frame prefix')
        size=struct.unpack('<I',prefix)[0];require(0<size<=8388608,'Water endpoint GPF frame cap')
        body=reader.read(size);require(len(body)==size,'Water endpoint complete frame body')
        yield body


def way_ends(body):
    require(len(body)>=FRAME_HEAD.size,'Water endpoint GPF header size')
    magic,kind,visible,reserved,identity,version=FRAME_HEAD.unpack_from(body)
    require(magic==b'GPF1' and kind==1 and visible==1 and reserved==0 and identity>0 and version>0,'Water endpoint GPF way header')
    cursor=FRAME_HEAD.size
    def number():
        nonlocal cursor
        require(cursor+4<=len(body),'Water endpoint truncated integer')
        value=struct.unpack_from('<I',body,cursor)[0];cursor+=4;return value
    def skip_string():
        nonlocal cursor
        size=number();require(size<=len(body)-cursor,'Water endpoint truncated string');cursor+=size
    skip_string();tags=number();require(tags<=(len(body)-cursor)//8,'Water endpoint tag count')
    for _ in range(tags):skip_string();skip_string()
    count=number();require(count>=2 and cursor+count*8==len(body),'Water endpoint exact reference layout')
    first=struct.unpack_from('<q',body,cursor)[0];last=struct.unpack_from('<q',body,len(body)-8)[0]
    require(first>0 and last>0,'Water endpoint native node identity')
    return identity,first,last,count


class Endpoints:
    def __init__(self,ids):
        self.ids=array('Q',ids);previous=0
        for identity in self.ids:require(previous<identity<2**63,'Water endpoint sorted unique member IDs');previous=identity
        require(len(self.ids)<=1000000 and self.ids.itemsize==8,'Water endpoint member capacity/platform')
        self.first=array('Q',[0])*len(self.ids);self.last=array('Q',[0])*len(self.ids)
        self.count=array('I',[0])*len(self.ids);self.found=bytearray(len(self.ids))

    def lookup(self,identity):
        rank=bisect_left(self.ids,identity)
        require(rank<len(self.ids) and self.ids[rank]==identity,'Water endpoint member absent from complete input closure')
        if not self.found[rank]:return None
        return identity,self.first[rank],self.last[rank],self.count[rank]

    def rows(self):
        for i,identity in enumerate(self.ids):yield ROW.pack(identity,self.first[i],self.last[i],self.count[i],self.found[i])


def extract(reader,ids,check=lambda:None):
    facts=Endpoints(ids);cursor=ways=refs=raw_bytes=previous=0
    for body in frames(reader):
        check();identity,first,last,count=way_ends(body)
        require(identity>previous,'Water endpoint source way order');previous=identity
        ways+=1;refs+=count;raw_bytes+=len(body)+4
        while cursor<len(facts.ids) and facts.ids[cursor]<identity:cursor+=1
        if cursor<len(facts.ids) and facts.ids[cursor]==identity:
            facts.first[cursor]=first;facts.last[cursor]=last;facts.count[cursor]=count;facts.found[cursor]=1;cursor+=1
    return facts,{'sourceWayRecords':ways,'sourceReferenceOccurrences':refs,'sourceRawGpfBytes':raw_bytes,
                  'memberWayIds':len(facts.ids),'foundMemberWays':sum(facts.found),
                  'missingMemberWayIds':[i for i,present in zip(facts.ids,facts.found) if not present],
                  'endpointFactsRawBytes':len(facts.ids)*ROW.size,'coordinatesExamined':False}


def audit(reader,facts,check=lambda:None):
    cursor=ways=refs=0
    def missing(rank):require(not facts.found[rank] and facts.first[rank]==facts.last[rank]==facts.count[rank]==0,'Water endpoint independent missing-row values')
    for body in frames(reader):
        check();row=decode_frame(body);require(row['type']=='way','Water endpoint independent GPF type')
        ways+=1;refs+=len(row['nodes'])
        while cursor<len(facts.ids) and facts.ids[cursor]<row['id']:missing(cursor);cursor+=1
        if cursor<len(facts.ids) and facts.ids[cursor]==row['id']:
            require(facts.found[cursor] and (facts.first[cursor],facts.last[cursor],facts.count[cursor])==
                    (row['nodes'][0],row['nodes'][-1],len(row['nodes'])),'Water endpoint every source member field independently exact')
            cursor+=1
    while cursor<len(facts.ids):missing(cursor);cursor+=1
    return {'allSavedSourceWaysDecoded':ways,'allSavedSourceReferencesDecoded':refs,'allMemberEndpointRowsChecked':cursor,
            'coordinatesOrPolygonValidityEstablished':False}


def relation_chains(row,facts):
    result={'relationId':row['id'],'rawType':row['tags'].get('type',''),'polygonValidityEstablished':False}
    members=[m for m in row['members'] if m['type']=='way'];ids=[m['ref'] for m in members]
    if result['rawType']!='multipolygon':return result|{'status':'not_direct_multipolygon'}
    if any(m['type']=='relation' for m in row['members']):return result|{'status':'nested_relation_roles_need_geometry_policy'}
    if len(set(ids))!=len(ids):return result|{'status':'duplicate_way_member_occurrence'}
    missing=[i for i in ids if facts.lookup(i) is None]
    if missing:return result|{'status':'missing_way_member','missingWayIds':missing}
    roles=sorted({m['role'] for m in members if m['role'] not in ('outer','inner')})
    if roles:return result|{'status':'way_role_requires_explicit_policy','rawRoles':roles}
    groups={role:join_degree_two([facts.lookup(m['ref']) for m in members if m['role']==role]) for role in ('outer','inner')}
    okay=all(g['allMembersJoined'] for g in groups.values()) and bool(groups['outer']['closedChains'])
    return result|{'status':'explicit_role_degree2_closed_chains' if okay else 'native_endpoint_topology_requires_geometry_or_missing_closure',
                   'outer':groups['outer'],'inner':groups['inner']}
