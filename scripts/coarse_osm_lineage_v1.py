"""Lossless geometric contraction with complete source-way lineage kept offline."""
from array import array
from bisect import bisect_left
import gzip,hashlib,heapq,math,struct,sys,time

from coarse_osm_backbone_v1 import (CAPS,PROFILES,REL_WAY,EDGE,read_nodes,analyze,contract,csr,raw_csr,components,shortest,point)
from coarse_path_features import distance_km
from coarse_timing_input import require


class Access:
    def __init__(self,g,nodes):
        self.selected=array('I',(i for i,d in enumerate(g.degree) if d));self.edge=array('i',[-1])*len(self.selected)
        self.prefix=array('d',[0.])*len(self.selected);self.suffix=array('d',[0.])*len(self.selected)
        self.mapping=array('i',[-1])*len(g.degree)
        for i,node in enumerate(self.selected):self.mapping[node]=i
        for edge,(first,last) in enumerate(zip(g.geometry_offsets,g.geometry_offsets[1:])):
            chain=g.geometry[first:last];lengths=[1000*distance_km(point(nodes,a),point(nodes,b)) for a,b in zip(chain,chain[1:])]
            for position,node in enumerate(chain[1:-1],1):
                if g.vertex_map[node]>=0:continue
                i=self.mapping[node];require(i>=0 and self.edge[i]<0,'Lineage unique internal native point')
                self.edge[i]=edge;self.prefix[i]=math.fsum(lengths[:position]);self.suffix[i]=math.fsum(lengths[position:])
                require(math.isclose(self.prefix[i]+self.suffix[i],g.meters[edge],rel_tol=1e-12,abs_tol=1e-7),'Lineage paid internal access partition')
        require(all(g.vertex_map[node]>=0 or self.edge[i]>=0 for i,node in enumerate(self.selected)),'Lineage missing native access point')
    def options(self,g,node):
        require(0<=node<len(self.mapping) and self.mapping[node]>=0,'Lineage node outside selected profile')
        vertex=g.vertex_map[node]
        if vertex>=0:return [(vertex,0.)]
        i=self.mapping[node];edge=self.edge[i]
        return [(g.starts[edge],self.prefix[i]),(g.ends[edge],self.suffix[i])]


def query(g,access,graph,source,target,work,caps,check):
    began=time.monotonic();sources=access.options(g,source);targets=access.options(g,target);best=math.inf
    if source==target:return 0.,0,time.monotonic()-began
    a,b=access.mapping[source],access.mapping[target]
    if access.edge[a]>=0 and access.edge[a]==access.edge[b]:best=abs(access.prefix[a]-access.prefix[b])
    offsets,neighbors,meters=graph;dist=array('d',[math.inf])*(len(offsets)-1);queue=[];settled=0
    for vertex,cost in sources:
        if cost<dist[vertex]:dist[vertex]=cost;heapq.heappush(queue,(cost,vertex))
    while queue:
        value,node=heapq.heappop(queue)
        if value!=dist[node]:continue
        if value>=best:break
        settled+=1;work[0]+=1;require(work[0]<=caps['querySettles'],'Lineage query settle cap')
        if settled%1024==0:check()
        for goal,cost in targets:
            if node==goal:best=min(best,value+cost)
        for i in range(offsets[node],offsets[node+1]):
            candidate=value+meters[i];to=neighbors[i]
            if candidate<dist[to] and candidate<best:dist[to]=candidate;heapq.heappush(queue,(candidate,to));require(len(queue)<=caps['queryHeap'],'Lineage query heap cap')
    return (None if math.isinf(best) else best),settled,time.monotonic()-began


def prepare(factory,*,snapshot,windows,caps=CAPS,check=lambda:None):
    with factory() as stream:nodes,receipt=read_nodes(stream,snapshot,check,caps)
    graphs,context=analyze(factory,nodes,receipt,windows,(PROFILES[1],),caps,check);g=graphs[0];old_vertices=len(g.vertices)
    g.vertices=array('I');g.vertex_map=array('i',[-1])*len(g.degree)
    for i,degree in enumerate(g.degree):
        g.flags[i]&=~REL_WAY
        if degree and g.flags[i]:g.vertex_map[i]=len(g.vertices);g.vertices.append(i)
    contract(factory,nodes,receipt,[g],caps,check)
    return nodes,g,receipt,context,old_vertices


def build(factory,*,snapshot,windows,baseline,caps=CAPS,writer=lambda name,payload:None,check=lambda:None):
    require(sys.byteorder=='little' and array('I').itemsize==4 and array('d').itemsize==8,'Lineage binary widths/order')
    require(set(caps)==set(CAPS) and all(type(v) is int and 0<v<=CAPS[k] for k,v in caps.items()),'Lineage finite exact caps')
    require(baseline['id']=='major-roads' and 0<len(windows)<=21,'Lineage profile/area boundary')
    nodes,g,receipt,context,old_vertices=prepare(factory,snapshot=snapshot,windows=windows,caps=caps,check=check)
    require(g.selected_ways==baseline['selectedWays'] and g.primitive_edges==baseline['primitiveEdges'],'Lineage unchanged profile/edge denominator')
    graph=csr(len(g.vertices),g.starts,g.ends,g.meters);raw=raw_csr(g,nodes);access=Access(g,nodes);work=[0];queries=[]
    for q in baseline['queries']:
        check();ids=q['sourceNodeIds'];indices=[bisect_left(nodes.ids,i) for i in ids]
        require(all(i<len(nodes.ids) and nodes.ids[i]==identity for i,identity in zip(indices,ids)),'Lineage original query source IDs')
        before,rs,rt=shortest(raw,*indices,work,caps,check);after,cs,ct=query(g,access,graph,*indices,work,caps,check)
        require((before is None)==(q['rawMeters'] is None)==(after is None) and (before is None or math.isclose(before,q['rawMeters'],rel_tol=1e-10,abs_tol=1e-6) and math.isclose(before,after,rel_tol=1e-10,abs_tol=1e-6)),'Lineage original native query distance changed')
        queries.append({'windowId':q['windowId'],'sourceNodeIds':ids,'rawMeters':before,'lineageMeters':after,'rawSettled':rs,'lineageSettled':cs,'rawSearchSeconds':rt,'lineageSearchSeconds':ct,'internalPointQueries':sum(g.vertex_map[i]<0 for i in indices)})
    before=components(raw,(i for i,d in enumerate(g.degree) if d),check);after=components(graph,range(len(g.vertices)),check)
    require(before['count']==after['count']==baseline['rawComponents']['count'],'Lineage native components changed')
    routing={'xy.i32':array('i',(value for i in g.vertices for value in (nodes.x[i],nodes.y[i]))),'offsets.u32':graph[0],'targets.u32':graph[1],'meters.f64':graph[2]}
    selected=access.selected;mapping=access.mapping
    geometry={'xy.i32':array('i',(value for i in selected for value in (nodes.x[i],nodes.y[i]))),'offsets.u32':g.geometry_offsets,'nodes.u32':array('I',(mapping[i] for i in g.geometry))}
    sizes={}
    for family,arrays in (('routing',routing),('geometry',geometry)):
        plain=packed=0
        for name,data in arrays.items():
            raw_bytes=data.tobytes();compressed=gzip.compress(raw_bytes,mtime=0);require(gzip.decompress(compressed)==raw_bytes,'Lineage deterministic lossless gzip')
            writer(f'{family}/{name}',raw_bytes);writer(f'{family}/{name}.gz',compressed);plain+=len(raw_bytes);packed+=len(compressed)
        sizes[family]={'rawBytes':plain,'gzipBytes':packed}
    provenance=bytearray()
    for values in zip(g.ways,g.first,g.last,g.starts,g.ends,g.meters):provenance.extend(EDGE.pack(*values))
    for name,data in (('edges.bin',provenance),('vertices.u32',g.vertices.tobytes()),('selected-nodes.u32',selected.tobytes()),('geometry-source-nodes.u32',g.geometry.tobytes()),('alias-edge.i32',access.edge.tobytes()),('alias-prefix.f64',access.prefix.tobytes()),('alias-suffix.f64',access.suffix.tobytes())):writer('provenance/'+name,data)
    return {'format':'native-way-lineage-geometry-prototype-v1','captureReceipt':receipt,'relationContext':context,'profile':PROFILES[1],
        'selectedWays':g.selected_ways,'selectedNativeNodes':len(selected),'primitiveEdges':g.primitive_edges,'oldAnchors':old_vertices,'anchors':len(g.vertices),'contractedEdges':len(g.starts),'geometryNodeOccurrences':len(g.geometry),
        'sizes':sizes,'queries':queries,'querySettles':work[0],'rawComponents':before,'lineageComponents':after,'internalNativePoints':sum(edge>=0 for edge in access.edge),
        'policy':'Full ordered source geometry and every source-way/reference range remain in offline provenance. Explicit relation nodes, tagged nodes, selected-degree junctions, way ends, original window boundaries and outside-area nodes remain anchors. Way membership alone does not require interior routing anchors.',
        'carPolicyReviewed':False,'etaQualified':False,'nationalArtifactBuilt':False,'vercelQualified':False,'modelChanged':False}
