"""Portable mirrors/tiny binary/source lineage proof; no ignored assets or worker."""
import gzip,hashlib,json,math,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(ok,message):
    if not ok:raise ValueError(message)

def verify(stage):
    freeze=load(HERE/('freeze-'+stage+'-v1.json'));plan_path=HERE/('plan-'+stage+'-v1.json');plan=load(plan_path);raw=HERE/('raw-'+stage+'-v1');closed=load(HERE/('closed-'+stage+'-v1.json'));artifacts=load(raw/'artifacts.json')
    check(sha(plan_path)==freeze['recipeSha256']==sha(raw/'execution-plan.json'),'Executed recipe binding')
    for name,pin in closed['files'].items():
        if name in artifacts:check(pin['bytes']==artifacts[name]['bytes'] and pin['sha256']==artifacts[name]['sha256'],'Closed binary roster');continue
        p=raw/name;check(p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],'Closed mirror '+name)
    for name,pin in plan['inputs'].items():
        if not name.startswith('data/'):check(sha(REPO/name)==pin,'Repository code binding '+name)
    initial=load(raw/'container-initial.json');host=initial['HostConfig'];final=load(raw/'container-result.json');metrics=load(raw/'metrics.json');events=dict(line.split() for line in metrics['memory.events'].splitlines())
    check(initial['Image']==plan['image'] and host['Memory']==host['MemorySwap']==2147483648 and host['NanoCpus']==1000000000 and host['NetworkMode']=='none' and host['ReadonlyRootfs'],'Isolation')
    check(all(not m['RW'] for m in initial['Mounts'] if m['Destination']!='/work'),'Readonly inputs')
    check(final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled'] and closed['independentWorkerAbsent'] and load(raw/'cleanup.json')['independentInspectAbsent'],'Closed lifecycle')
    check(metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and events['oom']==events['oom_kill']=='0' and closed['usage']['conservativeAllocatedBytes']<=268435456,'Resources')
    report=load(raw/'report.json');v=report['anchors'];e=report['contractedEdges'];n=report['selectedNativeNodes'];p=report['primitiveEdges']
    check(e==p-n+v and report['internalNativePoints']==n-v,'Full native point/edge partition arithmetic')
    check(report['sizes']['routing']['rawBytes']==12*v+24*e+4 and report['sizes']['geometry']['rawBytes']==8*n+4*p+8*e+4,'Exact source geometry/routing array arithmetic')
    check(report['rawComponents']['count']==report['lineageComponents']['count'],'Connectivity')
    check(all(report[key] is False for key in ('carPolicyReviewed','etaQualified','nationalArtifactBuilt','vercelQualified','modelChanged')),'No ordinary-car/app fit admission')
    if stage=='controls':
        check(load(raw/'controls.json')=={'tests':12,'successful':True,'failures':0,'errors':0,'skips':0},'Target Linux controls')
        tiny_path=HERE/'tiny-artifacts-v1.json';check(sha(tiny_path)==closed['tinyArtifactsSha256'],'Tiny bytes binding');tiny={name:bytes.fromhex(value) for name,value in load(tiny_path).items()}
        for name,payload in tiny.items():check(len(payload)==artifacts[name]['bytes'] and hashlib.sha256(payload).hexdigest()==artifacts[name]['sha256'],'Every tiny binary');
        for name,payload in tiny.items():
            if name.endswith('.gz'):check(gzip.decompress(payload)==tiny[name[:-3]],'Tiny deterministic lossless gzip')
        def unpack(name,kind):return list(struct.unpack('<'+kind*(len(tiny[name])//struct.calcsize('<'+kind)),tiny[name]))
        check(unpack('routing/xy.i32','i')==[0,0,20000,0] and unpack('routing/offsets.u32','I')==[0,1,2] and unpack('routing/targets.u32','I')==[1,0],'Independent tiny source endpoints/CSR')
        check(unpack('geometry/xy.i32','i')==[0,0,10000,0,20000,0] and unpack('geometry/offsets.u32','I')==[0,3] and unpack('geometry/nodes.u32','I')==[0,1,2],'Every tiny native coordinate/reference')
        check(unpack('provenance/vertices.u32','I')==[0,2] and unpack('provenance/selected-nodes.u32','I')==[0,1,2] and unpack('provenance/geometry-source-nodes.u32','I')==[0,1,2],'Independent tiny full source-node lineage')
        length=6371000*math.radians(.002);weights=unpack('routing/meters.f64','d');check(all(math.isclose(value,length,rel_tol=1e-12,abs_tol=1e-7) for value in weights),'Independent physical tiny chain length')
        way,first,last,a,b,meters=struct.unpack('<QIIIId',tiny['provenance/edges.bin']);check((way,first,last,a,b)==(1,0,2,0,1) and math.isclose(meters,length,abs_tol=1e-7),'Full source-way/range provenance')
        check(unpack('provenance/alias-edge.i32','i')==[-1,0,-1],'Generic internal point alias')
        for name in ('alias-prefix.f64','alias-suffix.f64'):
            values=unpack('provenance/'+name,'d');check(values[0]==values[2]==0 and math.isclose(values[1],length/2,abs_tol=1e-7),'Paid arbitrary native-point offsets')
        check(report['oldAnchors']==3 and v==2 and e==1 and report['relationContext']['relations']==1,'Metadata retained with actual contraction')
    else:
        baseline_path=HERE/'baseline-input-report-v1.json';check(sha(baseline_path)==closed['baselineReportSha256']==plan['inputs']['data/coarse-quality/us-osm-backbone-run-v1/report.json'],'Unchanged original validation input')
        baseline=next(row for row in load(baseline_path)['profiles'] if row['id']=='major-roads')
        check(report['selectedWays']==baseline['selectedWays']==28995 and n==baseline['selectedNativeNodes']==143560 and p==baseline['primitiveEdges']==148961,'Full original selected denominators')
        check(report['oldAnchors']==baseline['contractedVertices']==62520 and report['rawComponents']['count']==baseline['rawComponents']['count']==41,'Original topology scope')
        check(len(report['queries'])==len(baseline['queries'])==41,'All original native pairs')
        for actual,old in zip(report['queries'],baseline['queries']):
            check(actual['windowId']==old['windowId'] and actual['sourceNodeIds']==old['sourceNodeIds'],'No pair replacement')
            check((actual['lineageMeters'] is None)==(old['rawMeters'] is None) and (old['rawMeters'] is None or math.isclose(actual['lineageMeters'],old['rawMeters'],rel_tol=1e-10,abs_tol=1e-6)),'Original native-point geometric distance')
        check(report['captureReceipt']['sha256']==plan['inputs']['data/coarse-quality/us-osm-disk-capture-run-v1/extract/elements.jsonl'],'Unchanged capture source seal')

if __name__=='__main__':
    stages=('controls',) if len(sys.argv)>1 and sys.argv[1]=='controls' else ('controls','run')
    for stage in stages:verify(stage)
    print('PASS: '+','.join(stages)+' target controls, tiny physical/binary/metadata/native-point lineage, original cases, resources and ownership')
