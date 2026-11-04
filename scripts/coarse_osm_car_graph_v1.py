"""Captured-data directed static-car reference and compact CSR prototype.

This is a bounded Python prototype, not the national importer or deployed model.
"""
from array import array
from collections import Counter,defaultdict
from bisect import bisect_left
import hashlib,heapq,math,struct,time
from pathlib import Path

from import_roads import distance_m
from coarse_osm_car_policy_v1 import POLICY,way_policy,node_policy,restriction_policy,turn_allowed
from coarse_osm_car_codec_v1 import Costs,Reverses,ticks
from coarse_osm_attributes_v1 import validate_record
from coarse_osm_records import strict_json
from coarse_timing_input import require

BLOCKED,SIGNAL,REVERSAL=1,2,4
CAPS={'records':2000000,'inputBytes':1073741824,'rowBytes':8388608,'selectedNodes':2000000,'ways':100000,
      'references':4000000,'relations':10000,'arcs':1000000,'turnPairs':2000000,'querySettles':40000000,'queryHeap':1000000}


def read_array(path,code):
    data=array(code);data.frombytes(Path(path).read_bytes());return data


def load_geometry(root,report,artifacts,check=lambda:None):
    root=Path(root)
    for name,pin in artifacts.items():
        check();path=root/name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size==pin['bytes'],'Car lineage asset type/size')
        with path.open('rb') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==pin['sha256'],'Car lineage asset binding')
    selected=read_array(root/'provenance/selected-nodes.u32','I');xy=read_array(root/'geometry/xy.i32','i');source_vertices=read_array(root/'provenance/vertices.u32','I')
    require(len(selected)==report['selectedNativeNodes']<=CAPS['selectedNodes'] and len(xy)==2*len(selected),'Car selected geometry cardinality')
    mapping={source:i for i,source in enumerate(selected)};anchors=[mapping[source] for source in source_vertices]
    offsets=read_array(root/'geometry/offsets.u32','I');geometry=read_array(root/'geometry/nodes.u32','I');edges=list(struct.iter_unpack('<QIIIId',(root/'provenance/edges.bin').read_bytes()))
    require(len(edges)==report['contractedEdges'] and len(offsets)==len(edges)+1 and offsets[0]==0 and offsets[-1]==len(geometry),'Car source edge/geometry offsets')
    return {'selected':selected,'xy':xy,'anchors':anchors,'edges':edges,'offsets':offsets,'geometry':geometry}


def read_metadata(stream,geometry,expected,snapshot,check=lambda:None):
    selected=geometry['selected'];xy=geometry['xy'];ids=array('q');flags=bytearray(len(selected));degree=array('I',[0])*len(selected);ends=bytearray(len(selected));ways={};rules=[];closed=set();closed_nodes=set();stats=Counter();types=Counter();hasher=hashlib.sha256();rows=size=node_ordinal=cursor=memberships=0;previous=None;mapping={}
    while line:=stream.readline(CAPS['rowBytes']+1):
        check();rows+=1;size+=len(line);require(rows<=CAPS['records'] and size<=CAPS['inputBytes'] and len(line)<=CAPS['rowBytes'] and line.endswith(b'\n'),'Car captured input caps')
        hasher.update(line);record=strict_json(line);e=validate_record(record,snapshot);key=e['type'],e['id'];require(previous is None or previous<key,'Car captured typed order');previous=key;types[e['type']]+=1;memberships+=len(record['windowIds'])
        if e['type']=='node':
            if cursor<len(selected) and selected[cursor]==node_ordinal:
                require(round(e['lon']*1e7)==xy[2*cursor] and round(e['lat']*1e7)==xy[2*cursor+1],'Car selected coordinate identity')
                ids.append(e['id']);mapping[e['id']]=cursor;decision=node_policy(e['tags']);flags[cursor]=(BLOCKED if decision['blocked'] else 0)|(SIGNAL if decision['signal'] else 0)|(REVERSAL if decision['tagged'] else 0)
                stats['selectedTaggedNodes']+=decision['tagged'];stats['selectedBlockedNodes']+=decision['blocked'];stats['selectedSignalNodes']+=decision['signal'];cursor+=1
            node_ordinal+=1
        elif e['type']=='relation':
            require(types['relation']<=CAPS['relations'],'Car relation cap')
            for member in e['members']:
                if member['type']=='node' and member['ref'] in mapping:flags[mapping[member['ref']]]|=REVERSAL
            decision=restriction_policy(e);stats['relations:'+decision['status']]+=1
            if decision['status']=='via-node':rules.append(decision)
            elif decision['status']=='closed-unsupported':
                closed.update(decision['memberWays'])
                if not decision['memberWays']:closed_nodes.update(decision['memberNodes'])
        elif e['tags'].get('highway') in POLICY['roles']:
            require(len(ways)<CAPS['ways'],'Car selected way cap');refs=[mapping[n] for n in e['nodes']];require(len(refs)>=2,'Car selected way references');stats['majorReferences']+=len(refs);require(stats['majorReferences']<=CAPS['references'],'Car reference cap')
            ends[refs[0]]=ends[refs[-1]]=1
            for a,b in zip(refs,refs[1:]):degree[a]+=1;degree[b]+=1
            policy=way_policy(e['tags']);ways[e['id']]={'refs':refs,'policy':policy,'tags':e['tags']};stats['ways:'+str(policy.reason or 'way-eligible')]+=1
            if policy.reason is None:
                for direction in ('forward','backward'):
                    if getattr(policy,direction) is not None:
                        stats['eligibleDirections']+=1;stats['defaultSpeedDirections']+=getattr(policy,direction+'_default')
                stats['onewayWays']+=(policy.forward is None)!=(policy.backward is None)
    receipt={'rows':rows,'bytes':size,'sha256':hasher.hexdigest(),'types':dict(types),'memberships':memberships}
    require(receipt==expected and cursor==len(selected),'Car unchanged complete capture')
    anchors=set(geometry['anchors'])
    for i,d in enumerate(degree):
        if d and (d!=2 or ends[i]):flags[i]|=REVERSAL
        require(not flags[i] or i in anchors,'Car semantic point lost by geometric contraction')
    for identity in closed_nodes:
        if identity in mapping:flags[mapping[identity]]|=BLOCKED
    stats['unsupportedMemberWaysPresent']=sum(identity in ways for identity in closed)
    stats['supportedViaNodeRules']=len(rules)
    return {'ids':ids,'flags':flags,'ways':ways,'rules':rules,'closedWays':closed,'stats':dict(stats),'receipt':receipt}


class Graph:
    def __init__(self,geometry,metadata,*,raw=False,check=lambda:None):
        self.geometry=geometry;self.metadata=metadata;self.raw=raw;self.nodes=len(geometry['selected']);self.anchor_set=set(geometry['anchors']);self.vertices=list(range(self.nodes)) if raw else geometry['anchors'];self.vertex={node:i for i,node in enumerate(self.vertices)}
        self.arcs=[];self.fragments={};self.alias=[None]*self.nodes;self.outgoing=[[] for _ in range(self.nodes)];self.rules=defaultdict(list);self.work=0
        for rule in metadata['rules']:self.rules[rule['fromWay'],rule['via']].append(rule)
        for edge,values in enumerate(geometry['edges']):
            check();way,first,last,a,b,_=values;source=metadata['ways'][way];lo,hi=geometry['offsets'][edge:edge+2];chain=list(geometry['geometry'][lo:hi])
            require(chain==source['refs'][first:last+1] and chain[0]==geometry['anchors'][a] and chain[-1]==geometry['anchors'][b],'Car full source-way geometry partition')
            for position,node in enumerate(chain[1:-1],1):
                require(self.alias[node] is None and node not in self.anchor_set,'Car unique internal alias');self.alias[node]=(edge,position)
            policy=source['policy'];costs={}
            for direction,speed in ((1,policy.forward),(-1,policy.backward)):
                prefix=[0]
                if speed is not None:
                    for tail,head in zip(chain,chain[1:]):
                        x=geometry['xy'];p=[x[2*tail]/1e7,x[2*tail+1]/1e7];q=[x[2*head]/1e7,x[2*head+1]/1e7]
                        prefix.append(prefix[-1]+(0 if tail==head else max(1,math.ceil(distance_m(p,q)*3600/speed))))
                costs[direction]=prefix
            self.fragments[edge]={'chain':chain,'prefix':costs,'arcs':{}}
            if policy.reason or way in metadata['closedWays']:continue
            for direction,speed in ((1,policy.forward),(-1,policy.backward)):
                if speed is None:continue
                spans=range(len(chain)-1) if raw else (None,)
                for part in spans:
                    start,end=(0,len(chain)-1) if part is None else (part,part+1)
                    if chain[start]==chain[end] and (part is not None or all(n==chain[0] for n in chain)):continue
                    tail,head=(chain[start],chain[end]) if direction==1 else (chain[end],chain[start]);cost=costs[direction][end]-costs[direction][start]
                    self.arcs.append({'tail':tail,'head':head,'way':way,'edge':edge,'part':part,'dir':direction,'costMs':cost,'reverse':None})
        self.arcs.sort(key=lambda a:(a['tail'],a['edge'],-1 if a['part'] is None else a['part'],-a['dir']))
        require(len(self.arcs)<=CAPS['arcs'],'Car arc cap');lookup={}
        for i,arc in enumerate(self.arcs):
            lookup[arc['edge'],arc['part'],arc['dir']]=i;self.outgoing[arc['tail']].append(i)
            if not raw:self.fragments[arc['edge']]['arcs'][arc['dir']]=i
        for arc in self.arcs:arc['reverse']=lookup.get((arc['edge'],arc['part'],-arc['dir']))
        self.costs=Costs(arc['costMs'] for arc in self.arcs)

    def delay(self,incoming,following):
        a,b=self.arcs[incoming],self.arcs[following];require(a['head']==b['tail'],'Car disconnected transition');node=a['head'];flags=self.metadata['flags'][node];reverse=a['reverse']==following
        if flags&BLOCKED or reverse and not flags&REVERSAL:return None
        if not turn_allowed(a['way'],b['way'],reverse,self.rules.get((a['way'],int(self.metadata['ids'][node])),())):return None
        return (POLICY['signalDelayMs'] if flags&SIGNAL else 0)+(POLICY['uTurnDelayMs'] if reverse else 0)

    def query(self,source,target,*,quantized=False,check=lambda:None):
        require(type(source) is int and type(target) is int and 0<=source<self.nodes and 0<=target<self.nodes,'Car native query point')
        if source==target:return {'costMs':0,'fragments':0,'settled':0}
        scale=lambda cost:ticks(cost)*125 if quantized else cost
        source_internal=not self.raw and source not in self.vertex;target_internal=not self.raw and target not in self.vertex
        best=(math.inf,0);seeds=[];target_arcs={}
        if target_internal:
            edge,pos=self.alias[target];fragment=self.fragments[edge]
            for direction,arc in fragment['arcs'].items():
                p=fragment['prefix'][direction];target_arcs[arc]=p[pos] if direction==1 else p[-1]-p[pos]
        if source_internal:
            edge,pos=self.alias[source];fragment=self.fragments[edge]
            for direction,arc in fragment['arcs'].items():
                p=fragment['prefix'][direction];seeds.append((arc,scale(p[-1]-p[pos] if direction==1 else p[pos])))
                if target_internal and self.alias[target][0]==edge:
                    end=self.alias[target][1]
                    if direction==1 and end>=pos or direction==-1 and end<=pos:best=min(best,(scale(abs(p[end]-p[pos])),1))
        else:
            for arc in self.outgoing[source]:
                seeds.append((arc,self.costs.get(arc)*125 if quantized else self.arcs[arc]['costMs']))
                if arc in target_arcs:best=min(best,(scale(target_arcs[arc]),1))
        dist={};pending=[];settled=0
        for arc,cost in seeds:
            if (cost,1)<dist.get(arc,(math.inf,0)):dist[arc]=(cost,1);heapq.heappush(pending,(cost,1,arc))
        while pending:
            cost,count,arc=heapq.heappop(pending)
            if dist[arc]!=(cost,count):continue
            if cost>best[0]:break
            settled+=1;self.work+=1;require(self.work<=CAPS['querySettles'],'Car query settle cap')
            if settled%1024==0:check()
            head=self.arcs[arc]['head']
            if not target_internal and head==target:best=min(best,(cost,count))
            for following in self.outgoing[head]:
                delay=self.delay(arc,following)
                if delay is None:continue
                if following in target_arcs:best=min(best,(cost+delay+scale(target_arcs[following]),count+1))
                weight=self.costs.get(following)*125 if quantized else self.arcs[following]['costMs'];candidate=(cost+delay+weight,count+1)
                if candidate<dist.get(following,(math.inf,0)) and candidate[0]<=best[0]:
                    dist[following]=candidate;heapq.heappush(pending,(*candidate,following));require(len(pending)<=CAPS['queryHeap'],'Car query heap cap')
        return {'costMs':None if math.isinf(best[0]) else best[0],'fragments':0 if math.isinf(best[0]) else best[1],'settled':settled}

    def serialize(self,writer):
        require(not self.raw,'Car raw reference is not the proposed runtime');offsets=array('I',[0])
        for node in self.vertices:offsets.append(offsets[-1]+len(self.outgoing[node]))
        require(offsets[-1]==len(self.arcs),'Car CSR cardinality');targets=array('I',(self.vertex[a['head']] for a in self.arcs));reverse=Reverses(self.arcs,offsets,self.vertex);pairs=[]
        for i,arc in enumerate(self.arcs):
            for j in self.outgoing[arc['head']]:
                if self.delay(i,j) is None and not self.metadata['flags'][arc['head']]&BLOCKED and not (arc['reverse']==j and not self.metadata['flags'][arc['head']]&REVERSAL):
                    require(len(pairs)<CAPS['turnPairs'],'Car sparse turn pair cap');pairs.append((i,j))
        require(len(pairs)<=CAPS['turnPairs'],'Car sparse turn pair cap')
        x=self.geometry['xy'];arrays={'xy.i32':array('i',(v for n in self.vertices for v in (x[2*n],x[2*n+1]))),'offsets.u32':offsets,'targets.u32':targets,'costs.u16':self.costs.words,
            'cost-overflow-arcs.u32':self.costs.indices,'cost-overflow-ticks.u32':self.costs.values,'reverse.u8':reverse.words,'reverse-overflow-arcs.u32':reverse.indices,'reverse-overflow-targets.u32':reverse.values,
            'node-flags.u8':bytearray(self.metadata['flags'][n] for n in self.vertices),'forbidden-turns.u32':array('I',(v for pair in pairs for v in pair))}
        total=0
        for name,data in arrays.items():raw=bytes(data) if isinstance(data,bytearray) else data.tobytes();writer(name,raw);total+=len(raw)
        for i,arc in enumerate(self.arcs):require(reverse.get(i,self.vertex[arc['head']],offsets)==arc['reverse'],'Car reverse ordinal roundtrip')
        return {'vertices':len(self.vertices),'arcs':len(self.arcs),'payloadBytes':total,'costOverflowEntries':len(self.costs.indices),'reverseOverflowEntries':len(reverse.indices),'forbiddenTurnPairs':len(pairs),'scope':'Isolated captured-data payload; excludes source snapping/geography/runtime/search/JS/app/package overhead. No national extrapolation.'}
