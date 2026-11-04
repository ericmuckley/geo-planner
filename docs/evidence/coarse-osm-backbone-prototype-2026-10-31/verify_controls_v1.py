"""Saved Linux/native-graph controls and independent tiny binary proof."""
import contextlib
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import struct
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
saved=sys.argv
try:
    previous=folder.parent/'coarse-osm-extraction-2026-10-30/verify_disk_capture_run_v1.py';sys.argv=[str(previous)]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(previous),run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_backbone_v1 import validate,isolation
plan=load(folder/'backbone-plan-controls-v1.json');validate(plan);freeze=load(folder/'backbone-freeze-controls-v1.json');assert sha(folder/'backbone-plan-controls-v1.json')==freeze['recipeSha256']=='0d9410c5c4e52a5a9690e2e96b07aa1a6c1b4bd4c3817782fd467d9cef76d073'
assert sha(folder/'decision.json')==plan['selectedDecisionSha256']
for path,pin in plan['inputs'].items():
    if not path.startswith('data/'):assert sha(repo/path)==pin
for path,pin in freeze['newProducerFiles'].items():assert sha(repo/path)==pin
closed=load(folder/'backbone-closed-controls-v1.json');raw=folder/'backbone-raw/controls-v1'
assert closed['files']==len(closed['roster'])==49 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==31769
for name,row in closed['roster'].items():assert not row['ignoredLargeAsset'] and (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
assert closed['closerSha256']==sha(repo/'scripts/close_osm_backbone_v1.py')
isolation(load(raw/'container-initial.json'));state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent'] and load(folder/'backbone-cleanup-controls-v1.json')['independentlyAbsent']
assert load(raw/'controls.json')=={'tests':15,'successful':True,'failures':0,'errors':0,'skips':0}
metrics=load(raw/'metrics.json');assert metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and 'oom 0' in metrics['memory.events'] and 'oom_kill 0' in metrics['memory.events']
result=load(raw/'result.json');report=load(raw/'report.json');assert result['status']=='passed_native_geometry_backbone_prototype' and result['reportSha256']==sha(raw/'report.json') and result['artifactsSha256']==sha(raw/'artifacts.json')
assert report['captureReceipt']['types']=={'node':3,'way':1}
for name,row in load(raw/'artifacts.json').items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
for profile in report['profiles']:
    prefix=raw/profile['id'];assert profile['primitiveEdges']==2 and profile['contractedEdges']==1 and profile['contractedVertices']==2 and profile['geometryNodeOccurrences']==3
    assert struct.unpack('<4i',(prefix/'routing/xy.i32').read_bytes())==(0,0,20000,0)
    assert struct.unpack('<3I',(prefix/'routing/offsets.u32').read_bytes())==(0,1,2) and struct.unpack('<2I',(prefix/'routing/targets.u32').read_bytes())==(1,0)
    assert struct.unpack('<6i',(prefix/'geometry/xy.i32').read_bytes())==(0,0,10000,0,20000,0)
    assert struct.unpack('<2I',(prefix/'geometry/offsets.u32').read_bytes())==(0,3) and struct.unpack('<3I',(prefix/'geometry/nodes.u32').read_bytes())==(0,1,2)
    edge=struct.unpack('<QIIIId',(prefix/'provenance/edges.bin').read_bytes());assert edge[:5]==(1,0,2,0,1)
    expected=6371000*math.radians(.002);assert math.isclose(edge[-1],expected,rel_tol=1e-12,abs_tol=1e-7)
    assert all(math.isclose(v,expected,abs_tol=1e-7) for v in struct.unpack('<2d',(prefix/'routing/meters.f64').read_bytes()))
    assert profile['windows']['empty']['ways']==profile['windows']['empty']['verificationPairs']==0
    assert profile['routingDecodedBytes']==52 and profile['geometryDecodedBytes']==44
    assert len(profile['queries'])==1 and math.isclose(profile['queries'][0]['rawMeters'],profile['queries'][0]['contractedMeters'],abs_tol=1e-7)
    for path in prefix.rglob('*.gz'):assert gzip.decompress(path.read_bytes())==path.with_suffix('').read_bytes()
assert not any(report[k] for k in ('carPermissionReviewed','etaModelQualified','nationalFootprintQualified','vercelPackageQualified','modelChanged'))
run=load(raw/'run-summary.json');assert run['exitCode']==run['networkRequests']==run['pbfOrNativeHelperReads']==0 and run['seconds']<=660 and result['seconds']<=600
print(json.dumps({'linuxControls':15,'skips':0,'independentAllPairsFixtureOracle':True,'tinyBinaryAndGzipVerified':True,'trueNativeConnectivityAndLengthPreserved':True,'carCostsAndNationalVercelFitQualified':False,'workerAbsent':True},indent=2))
