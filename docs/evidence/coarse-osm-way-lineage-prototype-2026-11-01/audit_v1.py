"""Independent SQLite/source-way/serialized geometry/alias/query audit, no producer."""
from array import array
from bisect import bisect_left
from collections import Counter,defaultdict
import gzip,hashlib,importlib.util,json,math,sqlite3,struct,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
old=REPO/'docs/evidence/coarse-osm-backbone-prototype-2026-10-31/verify_run_v1.py'
spec=importlib.util.spec_from_file_location('sealed_graph_oracle',old);oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
load=oracle.load;sha=oracle.sha;read_array=oracle.read_array;meters=oracle.meters;inside=oracle.inside;intersects=oracle.intersects;Linked=oracle.Linked;shortest=oracle.shortest;component_count=oracle.component_count


def point_distance(neighbors,a,b,*,vertex_map,used_map,edge_data,alias,prefix,suffix,positions,edge_lengths,settles):
    def options(node):
        if node in vertex_map:return [(vertex_map[node],0.)]
        i=used_map[node];edge=edge_data[alias[i]];return [(edge[3],prefix[i]),(edge[4],suffix[i])]
    ia,ib=used_map[a],used_map[b];source=len(vertex_map);target=source+1;so=options(a);to=options(b);extra=defaultdict(list);direct=None
    for v,cost in so:extra[v].append((source,cost))
    for v,cost in to:extra[v].append((target,cost))
    if alias[ia]>=0 and alias[ia]==alias[ib]:
        first,last=sorted((positions[ia],positions[ib]));direct=math.fsum(edge_lengths[alias[ia]][first:last])
    def augmented(v):
        if v==source:return iter([*so,*([] if direct is None else [(target,direct)])])
        if v==target:return iter([*to,*([] if direct is None else [(source,direct)])])
        return iter([*neighbors(v),*extra.get(v,[])])
    return shortest(augmented,source,target,settles)


def audit():
    began=time.monotonic();plan=load(HERE/'plan-run-v1.json');closed=load(HERE/'closed-run-v1.json');root=REPO/plan['output'];report=load(root/'report.json');artifacts=load(root/'artifacts.json')
    capture=load(REPO/'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json');db_path=REPO/capture['root']/'extract/audit-selected.sqlite';pin=capture['roster']['extract/audit-selected.sqlite']
    assert db_path.stat().st_size==pin['bytes'] and sha(db_path)==pin['sha256']
    for name,pin in artifacts.items():assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']==closed['files'][name]['sha256']
    db=sqlite3.connect(db_path.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');assert db.execute('PRAGMA quick_check').fetchone()==('ok',)
    windows=plan['windows'];boxes={w['id']:w['bbox'] for w in windows};ids=array('q');xs=array('i');ys=array('i');common=bytearray()
    for identity,raw in db.execute("SELECT id,raw FROM objects WHERE kind='node' ORDER BY id"):
        e=json.loads(raw);assert identity==e['id'];ids.append(identity);xs.append(round(e['lon']*1e7));ys.append(round(e['lat']*1e7));flag=2 if e['tags'] else 0
        if not any(inside([e['lon'],e['lat']],box) for box in boxes.values()):flag|=64
        common.append(flag)
    assert len(ids)==1123919
    def point(i):return [xs[i]/1e7,ys[i]/1e7]
    def index(identity):
        i=bisect_left(ids,identity);assert i<len(ids) and ids[i]==identity;return i
    relation_ways=set();relation_ids=set();relation_relrefs=set();member_types=Counter();missing_nodes=member_count=0
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
    roles=set(report['profile']['roles']);degree=array('I',[0])*len(ids);flags=bytearray(len(ids));raw_graph=Linked(len(ids));ways=refs=primitive=0
    cursor=iter(db.execute("SELECT id,w FROM memberships WHERE kind='way' ORDER BY id,w"));member=next(cursor,None)
    for identity,raw in db.execute("SELECT id,raw FROM objects WHERE kind='way' ORDER BY id"):
        memberships=[]
        while member is not None and member[0]==identity:memberships.append(windows[member[1]]['id']);member=next(cursor,None)
        e=json.loads(raw)
        if e['tags'].get('highway') not in roles:continue
        chain=[index(n) for n in e['nodes']];ways+=1;refs+=len(chain);primitive+=len(chain)-1;flags[chain[0]]|=1;flags[chain[-1]]|=1
        for a,b in zip(chain,chain[1:]):
            degree[a]+=1;degree[b]+=1;pa,pb=point(a),point(b);raw_graph.edge(a,b,meters(pa,pb))
            if any(not (inside(pa,boxes[w]) and inside(pb,boxes[w])) and intersects(pa,pb,boxes[w]) for w in memberships):flags[a]|=16;flags[b]|=16
    assert member is None
    vertices=[]
    for i,d in enumerate(degree):
        if not d:continue
        flags[i]|=common[i]
        if d!=2:flags[i]|=32
        if flags[i]:vertices.append(i)
    actual_vertices=read_array(root/'provenance/vertices.u32','I');assert list(actual_vertices)==vertices
    vertex_map={node:i for i,node in enumerate(vertices)};used=[i for i,d in enumerate(degree) if d];used_map={node:i for i,node in enumerate(used)}
    assert list(read_array(root/'provenance/selected-nodes.u32','I'))==used
    assert list(read_array(root/'routing/xy.i32','i'))==[v for i in vertices for v in (xs[i],ys[i])]
    assert list(read_array(root/'geometry/xy.i32','i'))==[v for i in used for v in (xs[i],ys[i])]
    shape=read_array(root/'provenance/geometry-source-nodes.u32','I');shape_offsets=read_array(root/'geometry/offsets.u32','I');shape_runtime=read_array(root/'geometry/nodes.u32','I')
    assert len(shape)==len(shape_runtime) and all(used_map[a]==b for a,b in zip(shape,shape_runtime))
    alias=read_array(root/'provenance/alias-edge.i32','i');prefix=read_array(root/'provenance/alias-prefix.f64','d');suffix=read_array(root/'provenance/alias-suffix.f64','d');assert len(alias)==len(prefix)==len(suffix)==len(used)
    edge_data=list(struct.iter_unpack('<QIIIId',(root/'provenance/edges.bin').read_bytes()));edge_number=0;expected_compact=Linked(len(vertices));alias_seen=bytearray(len(used));positions=array('i',[-1])*len(used);edge_lengths=[]
    for identity,raw in db.execute("SELECT id,raw FROM objects WHERE kind='way' ORDER BY id"):
        e=json.loads(raw)
        if e['tags'].get('highway') not in roles:continue
        chain=[index(n) for n in e['nodes']];cuts=[0,*[j for j in range(1,len(chain)) if flags[chain[j]]]];assert cuts[-1]==len(chain)-1
        for first,last in zip(cuts,cuts[1:]):
            edge=edge_data[edge_number];assert edge[:5]==(identity,first,last,vertex_map[chain[first]],vertex_map[chain[last]])
            lengths=[meters(point(a),point(b)) for a,b in zip(chain[first:last],chain[first+1:last+1])]
            assert math.isclose(edge[5],math.fsum(lengths),rel_tol=1e-12,abs_tol=1e-7)
            lo,hi=shape_offsets[edge_number:edge_number+2];assert list(shape[lo:hi])==chain[first:last+1]
            for j,node in enumerate(chain[first+1:last],1):
                assert node not in vertex_map;i=used_map[node];assert not alias_seen[i] and alias[i]==edge_number;alias_seen[i]=1;positions[i]=j
                assert math.isclose(prefix[i],math.fsum(lengths[:j]),rel_tol=1e-12,abs_tol=1e-7) and math.isclose(suffix[i],math.fsum(lengths[j:]),rel_tol=1e-12,abs_tol=1e-7)
            expected_compact.edge(edge[3],edge[4],edge[5]);edge_lengths.append(lengths);edge_number+=1
    assert edge_number==len(edge_data)==report['contractedEdges'] and len(shape_offsets)==edge_number+1 and shape_offsets[-1]==len(shape)
    for i,node in enumerate(used):
        if node in vertex_map:assert alias[i]==-1 and prefix[i]==suffix[i]==0 and not alias_seen[i]
        else:assert alias_seen[i]
    offsets=read_array(root/'routing/offsets.u32','I');targets=read_array(root/'routing/targets.u32','I');weights=read_array(root/'routing/meters.f64','d')
    assert len(offsets)==len(vertices)+1 and offsets[0]==0 and offsets[-1]==len(targets)==len(weights)==2*edge_number
    def neighbors(v):return zip(targets[offsets[v]:offsets[v+1]],weights[offsets[v]:offsets[v+1]])
    for v in range(len(vertices)):assert sorted(neighbors(v))==sorted(expected_compact.neighbors(v))
    assert component_count(raw_graph.neighbors,used,len(ids))==component_count(neighbors,range(len(vertices)),len(vertices))==report['rawComponents']['count']==report['lineageComponents']['count']==41
    settles=[0];internal_endpoints=0
    fields=dict(vertex_map=vertex_map,used_map=used_map,edge_data=edge_data,alias=alias,prefix=prefix,suffix=suffix,positions=positions,edge_lengths=edge_lengths)
    for q in report['queries']:
        a,b=map(index,q['sourceNodeIds']);before=shortest(raw_graph.neighbors,a,b,settles);after=point_distance(neighbors,a,b,settles=settles,**fields)
        assert (before is None)==(after is None)==(q['lineageMeters'] is None)
        if before is not None:assert math.isclose(before,after,rel_tol=1e-10,abs_tol=1e-6) and math.isclose(after,q['lineageMeters'],rel_tol=1e-10,abs_tol=1e-6)
        internal_endpoints+=int(a not in vertex_map)+int(b not in vertex_map)
    assert len(report['queries'])==41 and internal_endpoints==sum(q['internalPointQueries'] for q in report['queries'])
    assert ways==report['selectedWays']==28995 and primitive==report['primitiveEdges']==148961 and len(used)==report['selectedNativeNodes']==143560 and len(vertices)==report['anchors'] and sum(alias_seen)==report['internalNativePoints']
    for path in root.rglob('*.gz'):assert gzip.decompress(path.read_bytes())==path.with_suffix('').read_bytes()
    db.close();assert time.monotonic()-began<600
    return {'status':'independent_complete_way_lineage_geometry_audit_passed','auditorSha256':sha(Path(__file__)),'oracleSha256':sha(old),'closedSha256':sha(HERE/'closed-run-v1.json'),'reportSha256':sha(root/'report.json'),
        'primitiveEdgesChecked':primitive,'contractedEdgesChecked':edge_number,'anchorsChecked':len(vertices),'selectedNativePointsChecked':len(used),'geometryOccurrencesChecked':len(shape),'internalNativeAliasesChecked':sum(alias_seen),
        'sourceWayMetadataPartitionsChecked':ways,'components':41,'originalNativeQueryPairsChecked':41,'internalQueryEndpointsChecked':internal_endpoints,'independentQuerySettles':settles[0],
        'secondsIncludingSQLiteAndArtifactHashesSourceGeometryAndSerializedQueries':time.monotonic()-began,'method':'Separate sealed read-only auditSQLite and source-native incidence/metadata/cuts; every full geometry/edge partition/alias; independent linked graph versus serializedCSR; augmented virtual-point Dijkstra versus raw source graph. No producer or PBF/fine read.',
        'pbfOrFineReads':0,'applicationDbReads':0,'modelChanged':False,'carPolicyReviewed':False,'etaQualified':False,'nationalArtifactBuilt':False,'vercelQualified':False}

if __name__=='__main__':
    result=audit()
    if '--record' in sys.argv:
        with (HERE/'independent-audit-v1.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
