"""Portable tiny/mirror proof; no source/native execution or ignored asset reads."""
from collections import Counter
import hashlib,json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
sys.path.insert(0,str(REPO/'scripts'))

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_bytes())
def check(ok,message):
    if not ok:raise ValueError(message)

def verify(stage):
    freeze=load(HERE/('freeze-'+stage+'-v1.json'));plan_path=HERE/('plan-'+stage+'-v1.json');plan=load(plan_path);closed=load(HERE/('closed-'+stage+'-v1.json'));raw=HERE/('raw-'+stage+'-v1')
    check(sha(plan_path)==freeze['recipeSha256']==sha(raw/'execution-plan.json'),'Recipe binding')
    for name,pin in closed['files'].items():
        if name.endswith('.bin') or name=='country-screen.so':continue
        p=raw/name;check(p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],'Mirror binding '+name)
    for name,pin in plan['inputs'].items():
        if not name.startswith('data/'):check(sha(REPO/name)==pin,'Repository code/evidence binding '+name)
    initial=load(raw/'container-initial.json');host=initial['HostConfig'];result=load(raw/'container-result.json')
    check(initial['Image']==plan['image'] and host['Memory']==host['MemorySwap']==4294967296 and host['NanoCpus']==2000000000 and host['NetworkMode']=='none' and host['ReadonlyRootfs'],'Observed isolation')
    check(all(not m['RW'] for m in initial['Mounts'] if m['Destination'] not in ('/work','/builder/work')),'Readonly inputs')
    check(result['State']['ExitCode']==result['clientExitCode']==0 and not result['State']['OOMKilled'] and closed['independentWorkerAbsent'] and load(raw/'cleanup.json')['independentInspectAbsent'],'Closed lifecycle')
    metrics=load(raw/'metrics-end.json');events=dict(line.split() for line in metrics['memory.events'].splitlines())
    check(metrics['memory.max']=='4294967296' and metrics['memory.swap.max']=='0' and events['oom']==events['oom_kill']=='0','Kernel memory/OOM')
    check(closed['usage']['conservativeAllocatedBytes']<=plan['caps']['ownedBytes'][stage],'Owned allocation')
    if stage=='build':return
    r=load(raw/'receipt.json');t=load(raw/'topology.json');c=t['counts']
    check(r['nativeEof'] and r['pythonProjectionFrames']==0 and c['complete']==1,'Complete native/typed census')
    check(c['references']==r['topologyReferences'] and c['endpointOccurrences']==2*r['topologyWays'] and c['totalDegree']==2*c['primitiveEdges'],'Occurrence accounting')
    check(c['contractedEdges']==c['primitiveEdges']-c['uniqueNodes']+c['anchors'],'Independent removed-degree-two edge arithmetic')
    check(c['routingArrayBytes']==12*c['anchors']+24*c['contractedEdges']+4 and c['fullGeometryArrayBytes']==8*c['uniqueNodes']+4*c['primitiveEdges']+8*c['contractedEdges']+4 and c['combinedArrayBytes']==c['routingArrayBytes']+c['fullGeometryArrayBytes'],'Exact prototype array arithmetic')
    if stage=='controls':
        check(load(raw/'controls.json')=={'tests':39,'successful':True,'skips':0,'errors':0,'failures':0},'Target controls')
        from coarse_osm_country_wire_v4 import reference_seal
        rows=load(raw/'fixture.json');check(reference_seal(rows)==r['semanticSha256'],'Independent complete synthetic field seal')
        roles={role+suffix for role in ('motorway','trunk','primary','secondary','tertiary') for suffix in ('','_link')}
        ways=[row for row in rows if row['type']=='way' and row['tags'].get('highway') in roles]
        tags={row['id'] for row in rows if row['type']=='node' and row['tags']};relations=[m for row in rows if row['type']=='relation' for m in row['members']]
        protected=tags|{m['ref'] for m in relations if m['type']=='node'};relation_ways={m['ref'] for m in relations if m['type']=='way'}
        degree=Counter();ends=set();nodes=set();expected_refs=[]
        for way in ways:
            seq=way['nodes'];nodes.update(seq);ends.update((seq[0],seq[-1]))
            if way['id'] in relation_ways:protected.update(seq)
            for a,b in zip(seq,seq[1:]):degree[a]+=1;degree[b]+=1
            for i,node in enumerate(seq):expected_refs.append([node,way['id'],1 if i in (0,len(seq)-1) else 2,int(i in (0,len(seq)-1))])
        anchors={node for node in nodes if degree[node]!=2 or node in ends or node in protected}
        expected_edges=sum(sum(node in anchors for node in way['nodes'])-1 for way in ways)
        check(c['uniqueNodes']==len(nodes) and c['anchors']==len(anchors) and c['contractedEdges']==expected_edges,'Independent tiny graph incidence/metadata/partition')
        decoded_path=HERE/'control-typed-rows-v1.json';check(sha(decoded_path)==closed['tinyDecodedRowsSha256'],'Tiny decoded binding');decoded=load(decoded_path)
        actual_refs=[]
        for name,pin in decoded.items():
            packed=b''.join(struct.pack(pin['format'],*row) for row in pin['rows']);check(hashlib.sha256(packed).hexdigest()==pin['sha256']==closed['files'][name]['sha256'],'Tiny actual binary binding')
            if '/refs-' in name:
                actual_refs.extend(pin['rows']);check(pin['rows']==sorted(pin['rows'],key=lambda v:(v[0],v[1],v[3],v[2])),'Native sorted chunk order')
        check(Counter(map(tuple,actual_refs))==Counter(map(tuple,expected_refs)),'Independent every reference sorted multiset')
        for event,prefix,expected in ((10,'tagged-',sorted(tags)),(12,'relation-nodes-',[m['ref'] for m in relations if m['type']=='node']),(13,'relation-ways-',[m['ref'] for m in relations if m['type']=='way'])):
            actual=[row[0] for name,pin in sorted(decoded.items()) if name.startswith('streams/'+prefix) for row in pin['rows']]
            check(actual==expected,'Every source metadata occurrence '+prefix)
            wire=b''.join(struct.pack('<Q',n) for n in expected);check(hashlib.sha256(wire).hexdigest()==t['streams'][{10:'tagged',12:'relation-nodes',13:'relation-ways'}[event]]['wireSha256'],'Independent metadata stream seal')
        wire=b''.join(struct.pack('<QQII',*row) for row in expected_refs);check(hashlib.sha256(wire).hexdigest()==t['streams']['refs']['wireSha256'],'Independent raw source reference seal')
    else:
        census=load(REPO/'docs/evidence/coarse-osm-national-footprint-2026-11-01/raw-run-v1/receipt.json')
        check(r['counts']=={'node':1606229364,'way':162688797,'relation':1624265} and r['semanticSha256']==census['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16','Original whole source counts/seal')
        check(r['histogram']==census['histogram'] and r['metadata']==census['metadata'],'Original exact role/metadata census')
        check(r['sourceIdentity']['sourceSha256']==plan['source']['sha256'] and r['sourceIdentity']['sourceMd5']==plan['source']['md5'] and r['sourceIdentity']['framingBytesRead']==r['postSourceHashBytes']==12229320016,'Complete raw/header/posthash guards')
        check(c['references']==48163649 and c['primitiveEdges']==43936411 and r['topologyWays']==4227238 and c['allTaggedNodeIds']==48142518,'Fixed profile/reference denominator')
    check(all(t[key] is False for key in ('modelChanged','graphAllocated','carPolicyReviewed','etaQualified','vercelQualified')),'No model/fit/permission admission')

if __name__=='__main__':
    stages=('build','controls') if len(sys.argv)>1 and sys.argv[1]=='controls' else ('build','controls','run')
    for stage in stages:verify(stage)
    print('PASS: '+','.join(stages)+' frozen bindings, native source guards, independent tiny streams/graph counts, resources and ownership')
