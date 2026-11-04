"""Small-mirror proof; no Docker/native/source/index/provider/DB access."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
sys.path.insert(0,str(REPO/'scripts'))

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_bytes())
def check(condition,message):
    if not condition:raise ValueError(message)


def verify(stage):
    frozen=load(HERE/('freeze-'+stage+'-v1.json'));plan_path=HERE/('plan-'+stage+'-v1.json');plan=load(plan_path)
    check(sha(plan_path)==frozen['recipeSha256'],'Recipe binding')
    closed=load(HERE/('closed-'+stage+'-v1.json'));raw=HERE/('raw-'+stage+'-v1')
    check(closed['independentWorkerAbsent'],'Independent absence')
    for name,pin in closed['files'].items():
        if name=='country-screen.so':continue
        p=raw/name;check(p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],'Mirror binding '+name)
    check(sha(raw/'execution-plan.json')==frozen['recipeSha256'],'Executed recipe')
    for name,pin in plan['inputs'].items():
        check(sha(REPO/name)==pin,'Code/tool binding '+name)
    initial=load(raw/'container-initial.json');host=initial['HostConfig']
    check(initial['Image']==plan['image'] and host['NetworkMode']=='none' and host['Memory']==host['MemorySwap']==4294967296 and host['NanoCpus']==2000000000 and host['ReadonlyRootfs'],'Isolation')
    check(all(not m['RW'] for m in initial['Mounts'] if m['Destination'] not in ('/work','/builder/work')),'Readonly inputs')
    final=load(raw/'container-result.json');check(final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled'],'Worker outcome')
    metrics=load(raw/'metrics-end.json');events=dict(line.split() for line in metrics['memory.events'].splitlines())
    check(metrics['memory.max']=='4294967296' and metrics['memory.swap.max']=='0' and events['oom']==events['oom_kill']=='0','Kernel resources')
    check(closed['usage']['conservativeAllocatedBytes']<=67108864,'Closed allocation')
    check(load(raw/'cleanup.json')['independentInspectAbsent'] and load(raw/'run-summary.json')['exitCode']==0,'Cleanup/outcome')
    if stage=='build':return
    receipt=load(raw/'receipt.json');check(receipt['nativeEof'] and receipt['pythonProjectionFrames']==0,'Complete metadata-only receipt')
    h=receipt['histogram'];t=h['totals'];roles=h['highwayRoles']
    if stage=='controls':
        controls=load(raw/'controls.json');check(controls=={'tests':23,'successful':True,'skips':0,'errors':0,'failures':0},'Linux controls')
        rows=load(raw/'fixture.json');expected={key:0 for key in t};road_expected={};restriction_expected={}
        for row in rows:
            kind=row['type'];expected[kind+'s']+=1;expected['tagged'+kind.title()+'s']+=bool(row['tags'])
            if kind=='way':
                n=len(row['nodes']);expected['allWayReferences']+=n;expected['allWayPrimitiveEdges']+=n-1
                if 'highway' in row['tags']:
                    expected['highwayWays']+=1;key=row['tags']['highway'];r=road_expected.setdefault(key,dict.fromkeys(('ways','references','primitiveEdges','wayEndOccurrences','closedWays','longWays','maxReferences'),0))
                    r['ways']+=1;r['references']+=n;r['primitiveEdges']+=n-1;r['wayEndOccurrences']+=2;r['closedWays']+=row['nodes'][0]==row['nodes'][-1];r['longWays']+=n>1024;r['maxReferences']=max(r['maxReferences'],n)
                else:
                    expected['nonHighwayWays']+=1;expected['nonHighwayReferences']+=n;expected['nonHighwayPrimitiveEdges']+=n-1
            if kind=='relation':
                restricted=row['tags'].get('type')=='restriction';expected['restrictionRelations']+=restricted
                for member in row['members']:
                    k=member['type'];expected['relation'+k.title()+'Members']+=1
                    if restricted:
                        expected['restriction'+k.title()+'Members']+=1
                        restriction_expected.setdefault(member['role'],{'node':0,'way':0,'relation':0})[k]+=1
        check(h=={'totals':expected,'highwayRoles':road_expected,'restrictionMemberRoles':restriction_expected},'Independent complete fixture counters')
        from coarse_osm_country_wire_v4 import reference_seal
        check(receipt['semanticSha256']==reference_seal(rows),'Independent original semantic seal')
    else:
        check(receipt['counts']=={'node':1606229364,'way':162688797,'relation':1624265} and receipt['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16','Whole-source original EOF/seal/counts')
        identity=receipt['sourceIdentity'];check(identity['sourceSha256']==plan['source']['sha256'] and identity['sourceMd5']==plan['source']['md5'] and identity['framingBytesRead']==receipt['postSourceHashBytes']==12229320016,'Full raw source framing/posthash')
        prior=load(REPO/'docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/summary.json')['receipt']
        check(receipt['metadata']==prior['metadata'],'Original source metadata')
        for key in ('references','members','tags','tagUtf8Bytes','maxReferences','maxMembers','maxTags','highwayWays','examinedHighwayReferences'):
            check(receipt[key]==prior[key],'Original counter '+key)
        check(t['highwayWays']==52053199 and sum(r['references'] for r in roles.values())==509547029,'Full highway denominator incl long ways')
    check(t['nodes']==receipt['counts'].get('node',0) and t['ways']==t['highwayWays']+t['nonHighwayWays']==receipt['counts'].get('way',0) and t['relations']==receipt['counts'].get('relation',0),'Typed total reconciliation')
    check(sum(r['ways'] for r in roles.values())==t['highwayWays'] and sum(r['references'] for r in roles.values())+t['nonHighwayReferences']==receipt['references'],'All roles/ref denominator')
    check(sum(r['primitiveEdges'] for r in roles.values())+t['nonHighwayPrimitiveEdges']==t['allWayPrimitiveEdges']==receipt['references']-t['ways'],'All primitive denominator')
    major={r+s for r in ('motorway','trunk','primary','secondary','tertiary') for s in ('','_link')}
    bounds=load(raw/'bounds.json')
    for profile,selected in (('all-highways',list(roles.values())),('major-roads',[v for k,v in roles.items() if k in major])):
        refs=sum(r['references'] for r in selected);edges=sum(r['references']-r['ways'] for r in selected);b=bounds[profile]
        check(b['referenceIdSpoolBytes']==8*refs and b['degreeRecordSpoolBytes']==16*refs and b['rawRoutingArrayUpperBytes']==12*refs+24*edges+4 and b['rawFullGeometryArrayUpperBytes']==8*refs+12*edges+4 and b['routingAndGeometryUpperBytes']==20*refs+36*edges+8,'Independent typed storage arithmetic')
    result=load(raw/'result.json');check(all(result[k] is False for k in ('modelChanged','graphAllocated','etaQualified','vercelQualified')),'No premature model/fit admission')

if __name__=='__main__':
    stage=sys.argv[1] if len(sys.argv)>1 else 'run'
    stages=('build','controls') if stage=='controls' else ('build','controls','run')
    for s in stages:verify(s)
    print('PASS: '+','.join(stages)+' bindings, Linux controls, independent counters/storage arithmetic, source seals and closed ownership')
