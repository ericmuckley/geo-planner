"""Portable frozen controls proof; no source, Docker, provider or application access."""
import hashlib,json,math,struct
from pathlib import Path

REPORT=Path(__file__).resolve().parent;REPO=REPORT.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((REPORT/n).read_bytes())
def verify():
    closed=read('car-closed-controls-v1.json');root=REPORT/'car-raw/controls-v1'
    for name,pin in closed['roster'].items():
        p=root/name;assert not pin['ignoredLargeAsset'] and p.is_file() and p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],name
    plan=json.loads((root/'execution-plan.json').read_bytes());assert sha(root/'execution-plan.json')==read('freeze-controls-v1.json')['recipeSha256']
    for name,pin in (plan['inputs']|plan['hostBindings']).items():assert sha(REPO/name)==pin,name
    controls=json.loads((root/'controls.json').read_bytes());assert controls=={'tests':26,'successful':True,'failures':0,'errors':0,'skips':0}
    result=json.loads((root/'result.json').read_bytes());assert result['reportSha256']==sha(root/'report.json') and result['artifactsSha256']==sha(root/'artifacts.json')
    data=json.loads((root/'report.json').read_bytes());assert not any(data[k] for k in ('etaQualified','nationalArtifactBuilt','vercelQualified','modelChanged'))
    artifacts=json.loads((root/'artifacts.json').read_bytes());assert sum(p['bytes'] for p in artifacts.values())==44==data['payload']['payloadBytes']
    # Independent tiny wire proof: two .001-degree equatorial steps, default55kph.
    primitive_ms=math.ceil(6371008.8*math.radians(.001)*3600/55);exact=2*primitive_ms;tick=(exact+124)//125
    expected={'xy.i32':struct.pack('<iiii',0,0,20000,0),'offsets.u32':struct.pack('<III',0,1,2),'targets.u32':struct.pack('<II',1,0),'costs.u16':struct.pack('<HH',tick,tick),'reverse.u8':bytes([0,0]),'node-flags.u8':bytes([4,4])}
    for name,pin in artifacts.items():
        b=(root/name).read_bytes();assert len(b)==pin['bytes'] and hashlib.sha256(b).hexdigest()==pin['sha256'];assert b==expected.get(name.removeprefix('routing/'),b''),name
    assert len(data['queries'])==2
    for q in data['queries']:assert q['raw']['costMs']==q['contracted']['costMs']==exact and q['quantized']['costMs']==q['binaryQuantizedMs']==tick*125
    metrics=json.loads((root/'metrics.json').read_bytes());events=dict(line.split() for line in metrics['memory.events'].splitlines());assert metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and int(metrics['memory.peak'])<=2147483648 and events['oom']==events['oom_kill']=='0'
    summary=json.loads((root/'run-summary.json').read_bytes());assert summary['exitCode']==summary['networkRequests']==summary['pbfOrNativeHelperReads']==0 and summary['seconds']<660
    final=json.loads((root/'container-result.json').read_bytes());assert final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled']
    assert json.loads((root/'cleanup.json').read_bytes())['independentInspectAbsent'] and read('car-cleanup-controls-v1.json')['independentlyAbsent']
    return {'qualified':True,'tests':26,'tinyWireBytes':44,'workerAbsent':True,'reads':'Small mirrored controls and source-code bindings only'}
if __name__=='__main__':print(json.dumps(verify()))
