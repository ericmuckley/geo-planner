"""Saved prototype proof; optional independent native graph/length audit.

Local mode reads new graph files and the separate sealed acquired-file audit
SQLite only. No country PBF/fine/native/provider/application database access.
"""
import argparse
from array import array
from bisect import bisect_left
from collections import Counter
import contextlib
import gzip
import hashlib
import heapq
import io
import json
import math
from pathlib import Path
import runpy
import sqlite3
import struct
import sys
import time

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def read_array(path,code):
    a=array(code);a.frombytes(path.read_bytes())
    if sys.byteorder!='little':a.byteswap()
    return a

def meters(a,b):
    x,y=map(math.radians,(a[1],b[1]));h=math.sin((y-x)/2)**2+math.cos(x)*math.cos(y)*math.sin(math.radians(b[0]-a[0])/2)**2
    return 12742000*math.atan2(math.sqrt(min(1,h)),math.sqrt(max(0,1-h)))

def intersects(a,b,box):
    lo,hi=0.,1.
    for axis in (0,1):
        d=b[axis]-a[axis]
        if not d:
            if not box[axis]<=a[axis]<=box[axis+2]:return False
        else:
            x=(box[axis]-a[axis])/d;y=(box[axis+2]-a[axis])/d;lo=max(lo,min(x,y));hi=min(hi,max(x,y))
            if hi<=lo:return False
    return True

def inside(p,b):return b[0]<=p[0]<=b[2] and b[1]<=p[1]<=b[3]


class Linked:
    def __init__(self,n):self.head=array('i',[-1])*n;self.next=array('i');self.to=array('I');self.length=array('d')
    def arc(self,a,b,length):
        self.next.append(self.head[a]);self.head[a]=len(self.to);self.to.append(b);self.length.append(length)
    def edge(self,a,b,length):self.arc(a,b,length);self.arc(b,a,length)
    def neighbors(self,n):
        i=self.head[n]
        while i>=0:yield self.to[i],self.length[i];i=self.next[i]


def shortest(neighbors,start,goal,limit):
    pending=[(0.,start)];dist={start:0.};done=set()
    while pending:
        value,n=heapq.heappop(pending)
        if n in done:continue
        done.add(n);limit[0]+=1;assert limit[0]<=80000000
        if n==goal:return value
        for to,length in neighbors(n):
            candidate=value+length
            if to not in done and candidate<dist.get(to,math.inf):dist[to]=candidate;heapq.heappush(pending,(candidate,to))
    return None


def component_count(neighbors,active,n):
    seen=bytearray(n);count=0
    for start in active:
        if seen[start]:continue
        count+=1;queue=array('I',[start]);seen[start]=1;pos=0
        while pos<len(queue):
            node=queue[pos];pos+=1
            for to,_ in neighbors(node):
                if not seen[to]:seen[to]=1;queue.append(to)
    return count


def local_audit(plan,closed,report):
    began=time.monotonic();old=folder.parent/'coarse-osm-extraction-2026-10-30';capture=load(old/'disk-capture-closed-run-v1.json');db_path=repo/capture['root']/'extract/audit-selected.sqlite'
    pin=capture['roster']['extract/audit-selected.sqlite'];assert db_path.stat().st_size==pin['bytes'] and sha(db_path)==pin['sha256']
    db=sqlite3.connect(db_path.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');assert db.execute('PRAGMA quick_check').fetchone()==('ok',)
    root=repo/closed['root']
    for name,row in closed['roster'].items():assert (root/name).stat().st_size==row['bytes'] and sha(root/name)==row['sha256']
    ids=array('q');xs=array('i');ys=array('i');common=bytearray();windows=plan['windows'];boxes={w['id']:w['bbox'] for w in windows}
    for identity,raw in db.execute("SELECT id,raw FROM objects WHERE kind='node' ORDER BY id"):
        e=json.loads(raw);ids.append(identity);xs.append(round(e['lon']*1e7));ys.append(round(e['lat']*1e7));flag=2 if e['tags'] else 0
        if not any(inside([e['lon'],e['lat']],b) for b in boxes.values()):flag|=64
        common.append(flag)
    assert len(ids)==1123919
    def point(i):return [xs[i]/1e7,ys[i]/1e7]
    def node_index(identity):
        i=bisect_left(ids,identity);assert i<len(ids) and ids[i]==identity;return i
    relation_ways=set();relation_ids=set();relation_relrefs=set();member_types=Counter();missing_nodes=0;member_count=0
    for identity,raw in db.execute("SELECT id,raw FROM objects WHERE kind='relation' ORDER BY id"):
        relation_ids.add(identity)
        for m in json.loads(raw)['members']:
            member_count+=1;member_types[m['type']]+=1
            if m['type']=='way':relation_ways.add(m['ref'])
            elif m['type']=='relation':relation_relrefs.add(m['ref'])
            else:
                i=bisect_left(ids,m['ref'])
                if i<len(ids) and ids[i]==m['ref']:common[i]|=4
                else:missing_nodes+=1
    all_way_ids={r[0] for r in db.execute("SELECT id FROM objects WHERE kind='way'")}
    assert report['relationContext']=={'relations':len(relation_ids),'memberOccurrences':member_count,'memberTypes':dict(member_types),'uniqueMemberWays':len(relation_ways),'missingMemberWayIds':len(relation_ways-all_way_ids),'missingMemberNodeOccurrences':missing_nodes,'missingMemberRelationIds':len(relation_relrefs-relation_ids),'ordinaryCarApplicabilityReviewed':False}
    results=[];total_queries=0;total_settles=[0]
    for profile,result in zip(plan['profiles'],report['profiles']):
        degree=array('I',[0])*len(ids);flags=bytearray(len(ids));raw_graph=Linked(len(ids));role_counts=Counter();counts={w['id']:{'ways':0,'references':0,'primitiveEdges':0} for w in windows};way_count=refs_count=primitive=0
        members_cursor=iter(db.execute("SELECT id,w FROM memberships WHERE kind='way' ORDER BY id,w"));member=next(members_cursor,None)
        for identity,raw in db.execute("SELECT id,raw FROM objects WHERE kind='way' ORDER BY id"):
            memberships=[]
            while member is not None and member[0]==identity:memberships.append(windows[member[1]]['id']);member=next(members_cursor,None)
            e=json.loads(raw)
            if profile['roles'] is not None and e['tags'].get('highway') not in profile['roles']:continue
            indices=[node_index(n) for n in e['nodes']];way_count+=1;refs_count+=len(indices);primitive+=len(indices)-1;role_counts[e['tags']['highway']]+=1
            flags[indices[0]]|=1;flags[indices[-1]]|=1
            if identity in relation_ways:
                for i in indices:flags[i]|=8
            for a,b in zip(indices,indices[1:]):
                degree[a]+=1;degree[b]+=1;pa,pb=point(a),point(b);raw_graph.edge(a,b,meters(pa,pb))
                if any(not (inside(pa,boxes[w]) and inside(pb,boxes[w])) and intersects(pa,pb,boxes[w]) for w in memberships):flags[a]|=16;flags[b]|=16
            for wid in memberships:
                c=counts[wid];c['ways']+=1;c['references']+=len(indices);c['primitiveEdges']+=len(indices)-1
        assert member is None
        vertices=[]
        for i,d in enumerate(degree):
            if not d:continue
            flags[i]|=common[i]
            if d!=2:flags[i]|=32
            if flags[i]:vertices.append(i)
        prefix=root/profile['id'];actual_vertices=read_array(prefix/'provenance/vertices.u32','I');assert list(actual_vertices)==vertices
        vertex_map={source:i for i,source in enumerate(vertices)};used=[i for i,d in enumerate(degree) if d];assert list(read_array(prefix/'provenance/selected-nodes.u32','I'))==used
        runtime_xy=read_array(prefix/'routing/xy.i32','i');assert list(runtime_xy)==[v for i in vertices for v in (xs[i],ys[i])]
        shape_xy=read_array(prefix/'geometry/xy.i32','i');assert list(shape_xy)==[v for i in used for v in (xs[i],ys[i])]
        geometry_source=read_array(prefix/'provenance/geometry-source-nodes.u32','I');geometry_offsets=read_array(prefix/'geometry/offsets.u32','I');geometry_runtime=read_array(prefix/'geometry/nodes.u32','I');used_map={source:i for i,source in enumerate(used)}
        assert len(geometry_source)==len(geometry_runtime) and all(used_map[a]==b for a,b in zip(geometry_source,geometry_runtime))
        edge_bytes=(prefix/'provenance/edges.bin').read_bytes();assert len(edge_bytes)%32==0;edges=iter(struct.iter_unpack('<QIIIId',edge_bytes));compact_expected=Linked(len(vertices));edge_number=0;lengths=[]
        for identity,raw in db.execute("SELECT id,raw FROM objects WHERE kind='way' ORDER BY id"):
            e=json.loads(raw)
            if profile['roles'] is not None and e['tags'].get('highway') not in profile['roles']:continue
            indices=[node_index(n) for n in e['nodes']];cuts=[0,*[j for j in range(1,len(indices)) if flags[indices[j]]]]
            assert cuts[-1]==len(indices)-1
            for first,last in zip(cuts,cuts[1:]):
                edge=next(edges);assert edge[:5]==(identity,first,last,vertex_map[indices[first]],vertex_map[indices[last]])
                expected=math.fsum(meters(point(a),point(b)) for a,b in zip(indices[first:last],indices[first+1:last+1]));assert math.isclose(edge[-1],expected,rel_tol=1e-12,abs_tol=1e-7)
                lo,hi=geometry_offsets[edge_number:edge_number+2];assert list(geometry_source[lo:hi])==indices[first:last+1]
                compact_expected.edge(edge[3],edge[4],edge[-1]);lengths.append(edge[-1]);edge_number+=1
        assert next(edges,None) is None and len(geometry_offsets)==edge_number+1 and geometry_offsets[-1]==len(geometry_source)
        offsets=read_array(prefix/'routing/offsets.u32','I');targets=read_array(prefix/'routing/targets.u32','I');weights=read_array(prefix/'routing/meters.f64','d')
        assert len(offsets)==len(vertices)+1 and offsets[0]==0 and offsets[-1]==len(targets)==len(weights)==2*edge_number
        for v in range(len(vertices)):
            assert sorted(zip(targets[offsets[v]:offsets[v+1]],weights[offsets[v]:offsets[v+1]]))==sorted(compact_expected.neighbors(v))
        def compact_neighbors(v):return zip(targets[offsets[v]:offsets[v+1]],weights[offsets[v]:offsets[v+1]])
        actual_components=component_count(raw_graph.neighbors,used,len(ids));compact_components=component_count(compact_neighbors,range(len(vertices)),len(vertices));assert actual_components==compact_components==result['rawComponents']['count']==result['contractedComponents']['count']
        assert result['selectedWays']==way_count and result['sourceReferences']==refs_count and result['primitiveEdges']==primitive and result['selectedNativeNodes']==len(used) and result['contractedVertices']==len(vertices) and result['contractedEdges']==edge_number and result['geometryNodeOccurrences']==len(geometry_source) and result['sourceRoles']==dict(role_counts)
        assert math.isclose(result['distanceMeters'],math.fsum(lengths),rel_tol=1e-12,abs_tol=1e-3)
        reasons={'sourceWayEnd':1,'taggedNode':2,'relationNode':4,'relationWay':8,'areaBoundary':16,'degreeNotTwo':32,'outsideArea':64};assert result['anchorReasons']=={name:sum(bool(flags[i]&bit) for i in vertices) for name,bit in reasons.items()}
        expected_pairs=[]
        for window in windows:
            wid=window['id'];ranked=heapq.nsmallest(4,((hashlib.sha256(canonical([profile['id'],wid,int(ids[i])])).hexdigest(),v,i) for v,i in enumerate(vertices) if inside(point(i),window['bbox'])))
            pairs=[(ranked[j][1:],ranked[j+1][1:]) for j in range(0,len(ranked)-1,2)]
            qs=[q for q in result['queries'] if q['windowId']==wid];assert len(qs)==len(pairs)
            for q,((a,sa),(b,sb)) in zip(qs,pairs):
                assert q['sourceNodeIds']==[ids[sa],ids[sb]];before=shortest(raw_graph.neighbors,sa,sb,total_settles);after=shortest(compact_neighbors,a,b,total_settles)
                assert (before is None)==(after is None)==(q['rawMeters'] is None)==(q['contractedMeters'] is None)
                if before is not None:assert math.isclose(before,after,rel_tol=1e-10,abs_tol=1e-6) and math.isclose(before,q['rawMeters'],rel_tol=1e-10,abs_tol=1e-6) and math.isclose(after,q['contractedMeters'],rel_tol=1e-10,abs_tol=1e-6)
            counts[wid]|={'verificationPairs':len(qs),'reachablePairs':sum(q['rawMeters'] is not None for q in qs),'unreachablePairs':sum(q['rawMeters'] is None for q in qs)}
        assert counts==result['windows'];total_queries+=len(result['queries'])
        for path in prefix.rglob('*.gz'):assert gzip.decompress(path.read_bytes())==path.with_suffix('').read_bytes()
        for category,field in [('routing','routing'),('geometry','geometry')]:
            files=list((prefix/category).iterdir());assert sum(p.stat().st_size for p in files if not p.name.endswith('.gz'))==result[field+'DecodedBytes'];assert sum(p.stat().st_size for p in files if p.name.endswith('.gz'))==result[field+'GzipBytes']
        results.append({'id':profile['id'],'primitiveEdgesChecked':primitive,'contractedEdgesChecked':edge_number,'nativeAnchorsChecked':len(vertices),'geometryOccurrencesChecked':len(geometry_source),'components':actual_components,'sampledDistancesChecked':len(result['queries'])})
        assert time.monotonic()-began<600
    db.close()
    return {'auditorSha256':sha(Path(__file__)),'closedRosterSha256':sha(folder/'backbone-closed-run-v1.json'),'reportSha256':sha(root/'report.json'),'completeIndependentNativeGraphAudit':True,'profiles':results,'sampledNativeLengthQueriesChecked':total_queries,'auditSettles':total_settles[0],'seconds':time.monotonic()-began,'method':'Independent sealed audit-SQLite native nodes/ways/memberships/relations, incidence and protected anchors; every source-edge partition/native geometry/length; independent linked adjacency versus serializedCSR; source-ranked pairs checked with separate raw/contracted Dijkstra. Shared source snapshot/crypto, no producer call or physical/ordinary-car/national accuracy admission.','pbfOrFineReads':0,'appDatabaseReads':0,'modelChanged':False,'etaModelQualified':False,'nationalFootprintQualified':False,'vercelPackageQualified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');parser.add_argument('--record',action='store_true');args=parser.parse_args();assert not args.record or args.local_assets
    saved=sys.argv
    try:
        sys.argv=[str(folder/'verify_controls_v1.py')]
        with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
    finally:sys.argv=saved
    from run_osm_backbone_v1 import validate,isolation
    plan=load(folder/'backbone-plan-run-v1.json');validate(plan);freeze=load(folder/'backbone-freeze-run-v1.json');assert sha(folder/'backbone-plan-run-v1.json')==freeze['recipeSha256']=='2a2e6384c5cd388e48a39d02971e66fd4b8e75231d8b54d03a604416711726f1' and sha(folder/'decision.json')==plan['selectedDecisionSha256']
    for path,pin in plan['inputs'].items():
        if not path.startswith('data/'):assert sha(repo/path)==pin
    for path,pin in freeze['newProducerFiles'].items():assert sha(repo/path)==pin
    closed=load(folder/'backbone-closed-run-v1.json');mirror=folder/'backbone-raw/run-v1';assert closed['files']==len(closed['roster'])==48 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==113260775 and closed['usage']['logicalBytes']<=268435456
    for name,row in closed['roster'].items():
        if not row['ignoredLargeAsset']:assert (mirror/name).stat().st_size==row['bytes'] and sha(mirror/name)==row['sha256']
    assert closed['closerSha256']==sha(repo/'scripts/close_osm_backbone_v1.py')
    isolation(load(mirror/'container-initial.json'));state=load(mirror/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
    assert load(mirror/'cleanup.json')['removed'] and load(mirror/'cleanup.json')['independentInspectAbsent'] and load(folder/'backbone-cleanup-run-v1.json')['independentlyAbsent']
    metrics=load(mirror/'metrics.json');assert metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and int(metrics['memory.peak'])<=2147483648 and 'oom 0' in metrics['memory.events'] and 'oom_kill 0' in metrics['memory.events']
    report=load(mirror/'report.json');result=load(mirror/'result.json');assert result['status']=='passed_native_geometry_backbone_prototype' and result['reportSha256']==sha(mirror/'report.json') and result['artifactsSha256']==sha(mirror/'artifacts.json')
    assert report['captureReceipt']['sha256']=='efc36dc058b198711cc2666a751c9fd60b52d37902efbb22e1cba8b5f30f91f4' and report['captureReceipt']['rows']==report['captureReceipt']['memberships']==1368072
    assert report['captureReceipt']['types']=={'node':1123919,'relation':4900,'way':239253} and len(report['profiles'])==2
    for expected,profile in zip(plan['profiles'],report['profiles']):
        assert profile['id']==expected['id'] and profile['roles']==expected['roles'] and profile['selectedWays']==plan['expectedSource']['profileWayCounts'][profile['id']]
        assert list(profile['windows'])==[w['id'] for w in plan['windows']] and profile['rawComponents']['count']==profile['contractedComponents']['count']
    assert report['profiles'][0]['primitiveEdges']==1290777
    assert not any(report[k] for k in ('carPermissionReviewed','etaModelQualified','nationalFootprintQualified','vercelPackageQualified','modelChanged'))
    run=load(mirror/'run-summary.json');assert run['exitCode']==run['networkRequests']==run['pbfOrNativeHelperReads']==0 and run['seconds']<=660 and result['seconds']<=600
    if args.local_assets:
        record=local_audit(plan,closed,report)
        if args.record:
            with (folder/'independent-audit-v1.json').open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
    else:
        record=load(folder/'independent-audit-v1.json');assert record['auditorSha256']==sha(Path(__file__)) and record['closedRosterSha256']==sha(folder/'backbone-closed-run-v1.json') and record['reportSha256']==result['reportSha256'] and record['completeIndependentNativeGraphAudit']
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
