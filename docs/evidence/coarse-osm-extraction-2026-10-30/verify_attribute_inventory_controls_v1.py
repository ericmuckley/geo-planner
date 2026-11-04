"""Saved synthetic inventory controls; no network/PBF/native or large-asset read."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_attribute_controls_v2.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_attribute_inventory_v1 import validate,isolation
plan=load(folder/'attribute-inventory-plan-controls-v1.json');validate(plan);freeze=load(folder/'attribute-inventory-freeze-controls-v1.json')
assert sha(folder/'attribute-inventory-plan-controls-v1.json')==freeze['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin
for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
closed=load(folder/'attribute-inventory-closed-controls-v1.json');raw=folder/'attribute-inventory-raw/controls-v1'
assert closed['files']==len(closed['roster'])==12 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==23734
for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
assert closed['closerSha256']==sha(repo/'scripts/close_osm_attribute_inventory_v1.py')
isolation(load(raw/'container-initial.json'));state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent'] and load(folder/'attribute-inventory-cleanup-controls-v1.json')['independentlyAbsent']
assert load(raw/'controls.json')=={'tests':8,'successful':True,'failures':0,'errors':0,'skips':0}
metrics=load(raw/'metrics.json');assert metrics['memory.max']=='536870912' and metrics['memory.swap.max']=='0' and 'oom_kill 0' in metrics['memory.events']
r=load(raw/'result.json');profile=load(raw/'inventory.json');assert r['status']=='passed_raw_metadata_inventory' and r['records']==4 and r['inventorySha256']==sha(raw/'inventory.json')
assert profile['types']=={'node':2,'relation':1,'way':1} and profile['occurrences']==8 and profile['wayReferences']==2
assert profile['inputBytes']==1470 and profile['inputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
a=profile['allCapturedHighways'];outer,inner=[w['allCapturedHighways'] for w in profile['windows']]
assert a['ways']==a['plainNumericWays']==a['speedScopeWays']==a['accessTagWays']==1 and a['unscopedNumericWays']==0
assert 111180<a['clippedMeters']<111200 and a['clippedMeters']==outer['clippedMeters'] and abs(a['clippedMeters']-2*inner['clippedMeters'])<.01
assert profile['barrierTagNodes']==1 and profile['baseSpeedStatusWays']=={'plain_numeric':1} and profile['baseSpeedUnitWays']=={'mph':1}
assert not any(profile[k] for k in ('sourceOrPublisherAdequacyQualified','permissionsReviewed','usableForTiming','usableLimitOrMatchingGateQualified','modelChanged'))
summary=load(raw/'run-summary.json');assert summary['exitCode']==summary['networkRequests']==summary['pbfOrNativeHelperReads']==0
print(json.dumps({'linuxInventoryControls':8,'skips':0,'tinyRawTagsGeometryAndOverlapsVerified':True,'carPermissionsUnreviewed':True,'usableLimitOrMatchingQualified':False,'workerAbsent':True,'nationalCapturedDataRead':False},indent=2))
