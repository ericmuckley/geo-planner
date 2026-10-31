"""Saved four-case replay proof; optional input hashes, no native/producer/PBF IO."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(f/'verify_controls.py'),run_name='__main__')
sys.path.insert(0,str(r/'scripts'))
from run_osm_lookup_v3 import validate,isolation
plan=load(f/'replay-plan.json');validate(plan)
assert sha(f/'replay-plan.json')==load(f/'replay-freeze.json')['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/') or args.local_assets:assert sha(r/name)==pin,name
closed=load(f/'replay-closed.json');raw=f/'replay-raw'
for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
assert (raw/'execution-plan.json').read_bytes()==(f/'replay-plan.json').read_bytes()
isolation(load(raw/'container-initial.json'),'controls')
state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
assert load(f/'replay-cleanup-audit.json')['independentAbsent']
result=load(raw/'result.json');cases=result['cases'];assert [row['kind'] for row in cases]==['old','new','new','old']
for number,case in enumerate(cases):
    recorded=load(raw/f'case-{number}.json');close=load(raw/f'case-{number}-close.json')
    assert all(case[key]==value for key,value in recorded.items())
    assert recorded['secondsBeforeRecordClose']<=close['secondsThroughRecordClose']==case['secondsThroughRecordClose']<plan['caps']['caseSeconds']
    assert case['references']==2135008 and case['orderedWitnessSha256']==plan['expectedWitnessSha256']
    assert case['statistics']==cases[0]['statistics']
    assert case['statistics']['authenticatedShardBytes']==9460848817<=plan['caps']['ioEach']
    assert case['statistics']['decodedRows']==69544680<=plan['caps']['rowsEach']
    assert case['statistics']['codecCalls']==16979<=plan['caps']['callsEach']
means={kind:{field:sum(case[field] for case in cases if case['kind']==kind)/2 for field in ('pointsSeconds','secondsThroughRecordClose')} for kind in ('old','new')}
assert means==result['means'] and means['new']['pointsSeconds']<=.9*means['old']['pointsSeconds']
assert means['new']['secondsThroughRecordClose']<=means['old']['secondsThroughRecordClose']
assert result['status']=='lookup_replay_passed' and result['performanceGatesPassed'] and not result['nationalPbfRead'] and not result['fullIndexAllocated'] and not result['modelChanged']
assert load(raw/'run-summary.json')['status']=='lookup_passed'
metrics=load(raw/'metrics-end.json');cgroup=metrics['latest']['cgroup']
assert int(cgroup['memory.peak'])==338923520<=4294967296 and 'oom 0\n' in cgroup['memory.events'] and 'oom_kill 0\n' in cgroup['memory.events']
assert metrics['observedWorkPeaks']['conservativeAllocatedBytes']<768*1024**2
assert all(not mount['Destination'].endswith('.pbf') for mount in load(raw/'container-initial.json')['Mounts'])
if args.local_assets:
    parent=f.parent/'coarse-osm-way-batch-2026-10-30';previous=sys.argv
    try:
        sys.argv=[str(parent/'verify_closed.py'),'--local-assets']
        with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
    finally:sys.argv=previous
print(json.dumps({'fourFixedCasesAndPerformanceGatesVerified':True,'coordinateOccurrences':8540032,'identicalIntegrityCacheIoRowsVerified':True,
                  'pointTimeImprovementPercent':100*(1-means['new']['pointsSeconds']/means['old']['pointsSeconds']),
                  'localInputsAndReferenceWitnessesVerified':args.local_assets,'nationalPbfRead':False},indent=2))
