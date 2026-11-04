"""Native geometry graph and conservative within-way contraction; no car costs."""
from array import array
from bisect import bisect_left
from collections import Counter
import gzip
import hashlib
import heapq
import math
import struct
import sys
import time

from coarse_osm_match_v1 import read_nodes
from coarse_osm_records import canonical,strict_json
from coarse_path_features import distance_km
from coarse_timing_input import require
from coarse_timing_parquet import clip_segment

CAPS={'records':2000000,'rowBytes':8388608,'inputBytes':1073741824,'nodeCanonicalBytes':268435456,'geometryReferences':4000000,
      'relationReferences':4000000,'edges':4000000,'chainReferences':8000000,'querySettles':20000000,'queryHeap':500000}
MAJOR=('motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link')
PROFILES=({'id':'all-highways','roles':None},{'id':'major-roads','roles':list(MAJOR)})
ENDPOINT,TAGGED,REL_NODE,REL_WAY,BOUNDARY,JUNCTION,OUTSIDE=1,2,4,8,16,32,64
EDGE=struct.Struct('<QIIIId')


def point(nodes,index):return [nodes.x[index]/10000000,nodes.y[index]/10000000]
def inside(p,box):return box[0]<=p[0]<=box[2] and box[1]<=p[1]<=box[3]
def selected(profile,way):return profile['roles'] is None or way['tags'].get('highway') in profile['roles']


class Scan:
    def __init__(self,stream,caps,check):self.stream=stream;self.caps=caps;self.check=check;self.rows=self.bytes=0;self.hash=hashlib.sha256();self.complete=False
    def __iter__(self):
        while line:=self.stream.readline(self.caps['rowBytes']+1):
            self.check();self.rows+=1;self.bytes+=len(line)
            require(len(line)<=self.caps['rowBytes'] and line.endswith(b'\n') and self.rows<=self.caps['records'] and self.bytes<=self.caps['inputBytes'],'Backbone input cap')
            self.hash.update(line);yield strict_json(line)
        self.complete=True
    def verify(self,receipt):
        require(self.complete and self.rows==receipt['rows'] and self.bytes==receipt['bytes'] and self.hash.hexdigest()==receipt['sha256'],'Backbone repeated input drift')


class Graph:
    def __init__(self,profile,count,windows):
        self.profile=profile;self.degree=array('I',[0])*count;self.flags=bytearray(count)
        self.starts=array('I');self.ends=array('I');self.meters=array('d');self.ways=array('Q');self.first=array('I');self.last=array('I')
        self.geometry=array('I');self.geometry_offsets=array('I',[0]);self.vertices=array('I');self.vertex_map=array('i',[-1])*count
        self.selected_ways=self.references=self.primitive_edges=0;self.roles=Counter();self.window_counts={w['id']:{'ways':0,'references':0,'primitiveEdges':0} for w in windows}
    def add(self,way,indices,first,last,nodes,caps):
        require(len(self.starts)<caps['edges'] and len(self.geometry)+last-first+1<=caps['chainReferences'],'Backbone edge/geometry cap')
        a,b=self.vertex_map[indices[first]],self.vertex_map[indices[last]];require(a>=0 and b>=0,'Backbone missing anchor')
        length=math.fsum(1000*distance_km(point(nodes,x),point(nodes,y)) for x,y in zip(indices[first:last],indices[first+1:last+1]))
        require(math.isfinite(length) and length>=0,'Backbone finite length')
        self.starts.append(a);self.ends.append(b);self.meters.append(length);self.ways.append(way['id']);self.first.append(first);self.last.append(last)
        self.geometry.extend(indices[first:last+1]);self.geometry_offsets.append(len(self.geometry))


def indices_for(nodes,refs):
    result=[]
    for identity in refs:
        i=bisect_left(nodes.ids,identity);require(i<len(nodes.ids) and nodes.ids[i]==identity,'Backbone missing native node');result.append(i)
    return result


def analyze(factory,nodes,receipt,windows,profiles,caps,check):
    count=len(nodes.ids);common=bytearray(count);graphs=[Graph(p,count,windows) for p in profiles];boxes={w['id']:w['bbox'] for w in windows}
    way_members=set();way_ids=array('q');relation_ids=set();referenced_relations=set();member_counts=Counter();missing_nodes=0;members=0;node_position=0
    with factory() as stream:
        scan=Scan(stream,caps,check)
        for record in scan:
            e=record['element'];kind=e['type']
            if kind=='node':
                require(e['id']==nodes.ids[node_position],'Backbone node receipt order')
                if e['tags']:common[node_position]|=TAGGED
                if not any(inside([e['lon'],e['lat']],box) for box in boxes.values()):common[node_position]|=OUTSIDE
                node_position+=1;continue
            if kind=='relation':
                relation_ids.add(e['id'])
                for member in e['members']:
                    members+=1;require(members<=caps['relationReferences'],'Backbone relation member cap');member_counts[member['type']]+=1;identity=member['ref']
                    if member['type']=='way':way_members.add(identity)
                    elif member['type']=='relation':referenced_relations.add(identity)
                    else:
                        i=bisect_left(nodes.ids,identity)
                        if i<len(nodes.ids) and nodes.ids[i]==identity:common[i]|=REL_NODE
                        else:missing_nodes+=1
                continue
            require(isinstance(e['tags'].get('highway'),str) and bool(e['tags']['highway']),'Backbone nonempty highway role')
            way_ids.append(e['id']);ids=indices_for(nodes,e['nodes']);require(all(w in boxes for w in record['windowIds']),'Backbone unknown source area')
            boundary=set()
            for a,b in zip(ids,ids[1:]):
                pa,pb=point(nodes,a),point(nodes,b)
                if any((interval:=clip_segment(pa,pb,boxes[w])) is not None and interval!=(0.,1.) for w in record['windowIds']):boundary.update((a,b))
            for g in graphs:
                if not selected(g.profile,e):continue
                g.selected_ways+=1;g.references+=len(ids);g.primitive_edges+=len(ids)-1;g.roles[e['tags'].get('highway','')]+=1
                g.flags[ids[0]]|=ENDPOINT;g.flags[ids[-1]]|=ENDPOINT
                for i in boundary:g.flags[i]|=BOUNDARY
                if e['id'] in way_members:
                    for i in ids:g.flags[i]|=REL_WAY
                for a,b in zip(ids,ids[1:]):g.degree[a]+=1;g.degree[b]+=1
                for wid in record['windowIds']:
                    c=g.window_counts[wid];c['ways']+=1;c['references']+=len(ids);c['primitiveEdges']+=len(ids)-1
        scan.verify(receipt)
    for g in graphs:
        for i,degree in enumerate(g.degree):
            if degree:
                g.flags[i]|=common[i]
                if degree!=2:g.flags[i]|=JUNCTION
                if g.flags[i]:g.vertex_map[i]=len(g.vertices);g.vertices.append(i)
    missing_ways=sum(not (i<len(way_ids) and way_ids[i]==identity) for identity in way_members for i in [bisect_left(way_ids,identity)])
    context={'relations':len(relation_ids),'memberOccurrences':members,'memberTypes':dict(member_counts),'uniqueMemberWays':len(way_members),'missingMemberWayIds':missing_ways,'missingMemberNodeOccurrences':missing_nodes,'missingMemberRelationIds':len(referenced_relations-relation_ids),'ordinaryCarApplicabilityReviewed':False}
    return graphs,context


def contract(factory,nodes,receipt,graphs,caps,check):
    with factory() as stream:
        scan=Scan(stream,caps,check)
        for record in scan:
            e=record['element']
            if e['type']!='way':continue
            ids=indices_for(nodes,e['nodes'])
            for g in graphs:
                if not selected(g.profile,e):continue
                first=0
                for last in range(1,len(ids)):
                    if g.flags[ids[last]]:
                        g.add(e,ids,first,last,nodes,caps);first=last
                require(first==len(ids)-1,'Backbone unclosed source way')
        scan.verify(receipt)


def csr(count,starts,ends,lengths):
    degree=array('I',[0])*count
    for a,b in zip(starts,ends):degree[a]+=1;degree[b]+=1
    offsets=array('I',[0])
    for d in degree:offsets.append(offsets[-1]+d)
    targets=array('I',[0])*offsets[-1];meters=array('d',[0.])*offsets[-1];cursor=array('I',offsets[:-1])
    for a,b,length in zip(starts,ends,lengths):
        i=cursor[a];targets[i]=b;meters[i]=length;cursor[a]+=1
        i=cursor[b];targets[i]=a;meters[i]=length;cursor[b]+=1
    require(all(cursor[i]==offsets[i+1] for i in range(count)),'Backbone CSR accounting')
    return offsets,targets,meters


def raw_csr(g,nodes):
    offsets=array('I',[0])
    for d in g.degree:offsets.append(offsets[-1]+d)
    targets=array('I',[0])*offsets[-1];meters=array('d',[0.])*offsets[-1];cursor=array('I',offsets[:-1])
    for first,last in zip(g.geometry_offsets,g.geometry_offsets[1:]):
        chain=g.geometry[first:last]
        for a,b in zip(chain,chain[1:]):
            length=1000*distance_km(point(nodes,a),point(nodes,b))
            i=cursor[a];require(i<offsets[a+1],'Backbone duplicate raw incidence');targets[i]=b;meters[i]=length;cursor[a]+=1
            i=cursor[b];require(i<offsets[b+1],'Backbone duplicate raw incidence');targets[i]=a;meters[i]=length;cursor[b]+=1
    require(offsets[-1]==2*g.primitive_edges and all(cursor[i]==offsets[i+1] for i in range(len(g.degree))),'Backbone missing raw incidence')
    return offsets,targets,meters


def components(graph,active,check):
    offsets,targets,_=graph;seen=bytearray(len(offsets)-1);sizes=[]
    for start in active:
        if seen[start]:continue
        queue=array('I',[start]);seen[start]=1;position=0
        while position<len(queue):
            n=queue[position];position+=1
            if position%4096==0:check()
            for i in range(offsets[n],offsets[n+1]):
                neighbor=targets[i]
                if not seen[neighbor]:seen[neighbor]=1;queue.append(neighbor)
        sizes.append(len(queue))
    return {'count':len(sizes),'vertices':sum(sizes),'largest':max(sizes,default=0)}


def shortest(graph,start,goal,work,caps,check):
    began=time.monotonic();offsets,targets,meters=graph;dist=array('d',[math.inf])*(len(offsets)-1);dist[start]=0.;queue=[(0.,start)];settled=0
    while queue:
        value,n=heapq.heappop(queue)
        if value!=dist[n]:continue
        settled+=1;work[0]+=1;require(work[0]<=caps['querySettles'],'Backbone verification search cap')
        if settled%1024==0:check()
        if n==goal:return value,settled,time.monotonic()-began
        for i in range(offsets[n],offsets[n+1]):
            to=targets[i];candidate=value+meters[i]
            if candidate<dist[to]:dist[to]=candidate;heapq.heappush(queue,(candidate,to));require(len(queue)<=caps['queryHeap'],'Backbone verification heap cap')
    return None,settled,time.monotonic()-began


def verify_queries(g,nodes,windows,compact,raw,caps,check):
    work=[0];records=[]
    for window in windows:
        name=window['id'];ranked=heapq.nsmallest(4,((hashlib.sha256(canonical([g.profile['id'],name,int(nodes.ids[i])])).hexdigest(),v,i) for v,i in enumerate(g.vertices) if inside(point(nodes,i),window['bbox'])))
        for j in range(0,len(ranked)-1,2):
            _,a,sa=ranked[j];_,b,sb=ranked[j+1];before,rs,rt=shortest(raw,sa,sb,work,caps,check);after,cs,ct=shortest(compact,a,b,work,caps,check)
            require((before is None)==(after is None) and (before is None or math.isclose(before,after,rel_tol=1e-10,abs_tol=1e-6)),'Backbone distance/reachability changed')
            records.append({'windowId':name,'sourceNodeIds':[int(nodes.ids[sa]),int(nodes.ids[sb])],'rawMeters':before,'contractedMeters':after,'rawSettled':rs,'contractedSettled':cs,'rawSearchSeconds':rt,'contractedSearchSeconds':ct})
    return records,work[0]


def emit_graph(g,nodes,windows,writer,caps,check):
    prefix=g.profile['id'];compact=csr(len(g.vertices),g.starts,g.ends,g.meters);raw=raw_csr(g,nodes)
    raw_components=components(raw,(i for i,d in enumerate(g.degree) if d),check);contracted_components=components(compact,range(len(g.vertices)),check)
    require(raw_components['count']==contracted_components['count'],'Backbone component count changed')
    queries,settled=verify_queries(g,nodes,windows,compact,raw,caps,check)
    for wid,counts in g.window_counts.items():
        group=[q for q in queries if q['windowId']==wid];counts['verificationPairs']=len(group);counts['reachablePairs']=sum(q['rawMeters'] is not None for q in group);counts['unreachablePairs']=sum(q['rawMeters'] is None for q in group)
    routing={'xy.i32':array('i',(v for i in g.vertices for v in (nodes.x[i],nodes.y[i]))),'offsets.u32':compact[0],'targets.u32':compact[1],'meters.f64':compact[2]}
    runtime_bytes=packed_bytes=0
    for name,data in routing.items():
        payload=data.tobytes();runtime_bytes+=len(payload);writer(prefix+'/routing/'+name,payload);packed=gzip.compress(payload,mtime=0);require(gzip.decompress(packed)==payload,'Backbone lossless gzip roundtrip');packed_bytes+=len(packed);writer(prefix+'/routing/'+name+'.gz',packed)
    used=array('I',(i for i,d in enumerate(g.degree) if d));mapping=array('i',[-1])*len(nodes.ids)
    for n,i in enumerate(used):mapping[i]=n
    geometry={'xy.i32':array('i',(v for i in used for v in (nodes.x[i],nodes.y[i]))),'offsets.u32':g.geometry_offsets,'nodes.u32':array('I',(mapping[i] for i in g.geometry))}
    geometry_bytes=geometry_packed=0
    for name,data in geometry.items():
        payload=data.tobytes();geometry_bytes+=len(payload);writer(prefix+'/geometry/'+name,payload);packed=gzip.compress(payload,mtime=0);require(gzip.decompress(packed)==payload,'Backbone geometry gzip roundtrip');geometry_packed+=len(packed);writer(prefix+'/geometry/'+name+'.gz',packed)
    provenance=bytearray()
    for values in zip(g.ways,g.first,g.last,g.starts,g.ends,g.meters):provenance.extend(EDGE.pack(*values))
    writer(prefix+'/provenance/edges.bin',provenance);writer(prefix+'/provenance/vertices.u32',g.vertices.tobytes());writer(prefix+'/provenance/geometry-source-nodes.u32',g.geometry.tobytes());writer(prefix+'/provenance/selected-nodes.u32',used.tobytes())
    reasons={name:sum(bool(g.flags[i]&flag) for i in g.vertices) for name,flag in [('sourceWayEnd',ENDPOINT),('taggedNode',TAGGED),('relationNode',REL_NODE),('relationWay',REL_WAY),('areaBoundary',BOUNDARY),('degreeNotTwo',JUNCTION),('outsideArea',OUTSIDE)]}
    return {'id':prefix,'roles':g.profile['roles'],'selectedWays':g.selected_ways,'selectedNativeNodes':len(used),'sourceReferences':g.references,'primitiveEdges':g.primitive_edges,'contractedVertices':len(g.vertices),'contractedEdges':len(g.starts),'geometryNodeOccurrences':len(g.geometry),
            'primitiveToContractedEdgeReduction':1-len(g.starts)/g.primitive_edges if g.primitive_edges else None,'rawComponents':raw_components,'contractedComponents':contracted_components,'anchorReasons':reasons,'sourceRoles':dict(g.roles),'windows':g.window_counts,
            'routingDecodedBytes':runtime_bytes,'routingGzipBytes':packed_bytes,'geometryDecodedBytes':geometry_bytes,'geometryGzipBytes':geometry_packed,'queries':queries,'verificationSettles':settled,
            'distanceMeters':math.fsum(g.meters),'undirectedGeometryOnly':True,'carPermissionReviewed':False,'etaModelQualified':False,'nationalFootprintQualified':False,'vercelPackageQualified':False,'modelChanged':False}


def build(factory,*,snapshot,windows,profiles=PROFILES,caps=CAPS,writer=lambda name,payload:None,check=lambda:None):
    require(sys.byteorder=='little' and array('I').itemsize==4 and array('Q').itemsize==8 and array('d').itemsize==8,'Backbone binary widths/order')
    require(set(caps)==set(CAPS) and all(type(v) is int and 0<v<=CAPS[k] for k,v in caps.items()),'Backbone finite exact caps')
    require(0<len(windows)<=21 and profiles==PROFILES,'Backbone fixed profiles/area count')
    require(len({w['id'] for w in windows})==len(windows) and all(isinstance(w['id'],str) and 0<len(w['id'])<=128 and len(w['bbox'])==4 and all(type(v) in (int,float) and math.isfinite(v) for v in w['bbox']) and -180<=w['bbox'][0]<w['bbox'][2]<=180 and -90<=w['bbox'][1]<w['bbox'][3]<=90 for w in windows),'Backbone valid unique areas')
    with factory() as stream:nodes,receipt=read_nodes(stream,snapshot,check,caps)
    graphs,relations=analyze(factory,nodes,receipt,windows,profiles,caps,check);contract(factory,nodes,receipt,graphs,caps,check)
    return {'format':'native-osm-geometry-backbone-prototype-v1','captureReceipt':receipt,'relationContext':relations,'profiles':[emit_graph(g,nodes,windows,writer,caps,check) for g in graphs],
            'undirectedGeometryOnly':True,'carPermissionReviewed':False,'etaModelQualified':False,'nationalFootprintQualified':False,'vercelPackageQualified':False,'modelChanged':False,
            'scope':'All captured native highway geometry and fixed major-road subset; conservative within-way contraction with exact geometry/length/native-ID/metadata boundaries. Degree is within acquired capture, not globalOSM. No car direction/access/turn permission or timing cost. Sampled length-search validation is not ETA accuracy, national reachability, first app estimate or Vercel package proof.'}
