"""Closed native adapter/connected geometry controls; no real source input read."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2]
load=lambda p:json.loads(p.read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_continuous_match_run_v1.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_continuous_match_v2 import validate,isolation
plan=load(folder/'continuous-match-plan-controls-v2.json');validate(plan);freeze=load(folder/'continuous-match-freeze-controls-v2.json')
assert sha(folder/'continuous-match-plan-controls-v2.json')==freeze['recipeSha256']=='26c8ae76d10a70a41efdb0f00bda054340bc8686baa7f6b7c41647273d5f458f'
for path,pin in plan['inputs'].items():
    if not path.startswith('data/'):assert sha(repo/path)==pin
for path,pin in freeze['newProducerFiles'].items():assert sha(repo/path)==pin
closed=load(folder/'continuous-match-closed-controls-v2.json');raw=folder/'continuous-match-raw/controls-v2'
assert closed['files']==len(closed['roster'])==18 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==30899
for name,row in closed['roster'].items():assert not row['ignoredLargeAsset'] and (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
assert closed['closerSha256']==sha(repo/'scripts/close_osm_continuous_match_v2.py')
isolation(load(raw/'container-initial.json'));state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent'] and load(folder/'continuous-match-cleanup-controls-v2.json')['independentlyAbsent']
assert load(raw/'controls.json')=={'tests':19,'successful':True,'failures':0,'errors':0,'skips':0}
metrics=load(raw/'metrics.json');assert metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and 'oom 0' in metrics['memory.events'] and 'oom_kill 0' in metrics['memory.events']
result=load(raw/'result.json');profile=load(raw/'report.json');assert result['status']=='passed_continuous_geometry_diagnostic' and result['reportSha256']==sha(raw/'report.json') and result['reviewSha256']==sha(raw/'review-selection.json')
assert profile['captureReceipt']['types']=={'node':3,'way':2} and profile['allWindows']['arcWindowRecords']==1 and profile['allWindows']['sourceKm']==7 and profile['allWindows']['samples']==45 and profile['allWindows']['cappedRecords']==0
assert profile['allWindows']['singleGeometricPathRecords']==1 and profile['allWindows']['singlePathUnscopedNumericSupportedKm']==0
match=json.loads((raw/'windows/a/matches.jsonl').read_bytes());assert match['status']=='single_acquired_file_geometric_path' and len(match['candidates'])==1 and len(match['candidates'][0]['nativeParts'])==2
bindings=[json.loads(line) for line in (raw/'windows/a/part-bindings.jsonl').read_bytes().splitlines()]
assert len(bindings)==2 and [r['nativeWayId'] for r in bindings]==[1,2] and bindings[0]['endpointIds'][1]==bindings[1]['endpointIds'][0]==2
assert all(r['nativeTags']['access']=='private' and r['attributes']['speed']['kmh']==88.51392 and not r['attributes']['unscopedNumeric'] and r['attributes']['carPermission']=='unreviewed' and not r['attributes']['usableForTiming'] for r in bindings)
review=load(raw/'review-selection.json');assert len(review['records'])==1 and not review['physicalMatchReviewed']
assert not any(profile[k] for k in ('sourceAdequacyQualified','carPermissionReviewed','uniquePhysicalMatchQualified','usableLimitOrMatchingQualified','modelChanged'))
run=load(raw/'run-summary.json');assert run['exitCode']==run['networkRequests']==run['pbfOrNativeHelperReads']==0 and run['seconds']<=1860 and result['seconds']<=1800
zero=load(raw/'zero-midpoint-control.json');assert zero['status']=='single_acquired_file_geometric_path' and zero['sampleCount']==45 and zero['sourceKm']==7 and zero['zeroOriginalSampleVariants']==1 and len(zero['candidates'][0]['nativeParts'])==3 and zero['candidates'][0]['maximumSupportedKm']==7
assert result['reportSha256']==plan['expectedControlReportSha256']=='3d1b41c57c74fa1bea57d1377d62bc92ab25f77962bd9e233ee889faef1ee1fe'
print(json.dumps({'linuxControls':19,'byteIdenticalGeometryOutputs':True,'compactAggregationEquivalence':True,'skips':0,'nativeNodeIdentityAndSharedJunctionsVerified':True,'independentStraightSourceGraphOracleChecked':True,'zeroMidpointConnectorWithUnchangedWeights':True,'syntheticSplitPathAndOriginalWeightVerified':True,'carPermissionAndTimingUnreviewed':True,'workerAbsent':True,'actualCapturedDataRead':False},indent=2))
