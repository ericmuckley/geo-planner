"""Saved real bank-cap failure proof; optional closed-prefix hashes, never PBF/native."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_text())
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_cell_census_controls_v1.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_cell_census_v1 import validate,isolation
plan=load(folder/'cell-census-plan-run-v1.json');validate(plan)
assert sha(folder/'cell-census-plan-run-v1.json')==load(folder/'cell-census-freeze-run-v1.json')['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
closed=load(folder/'cell-census-closed-run-v1.json');raw=folder/'cell-census-raw/run-v1'
assert closed['files']==len(closed['roster'])==60 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==2080605918
assert closed['conservativeAllocatedBytes']==2082320384
assert {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}=={name for name,row in closed['roster'].items() if not row['ignoredPart']}
parts=[]
for name,row in closed['roster'].items():
    if row['ignoredPart']:
        assert Path(name).parent.as_posix()=='pass-a/bank' and Path(name).stem.isdigit() and 0<row['bytes']<=67108864
        parts.append(name)
    else:assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],name
assert len(parts)==31 and sum(closed['roster'][p]['bytes'] for p in parts)==2080277463
isolation(load(raw/'container-initial.json'),'controls')
final=load(raw/'container-result.json');assert final['State']['ExitCode']==final['clientExitCode']==2 and not final['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
assert load(folder/'cell-census-cleanup-run-v1.json')['independentAbsent']
failure=load(raw/'worker-failure.json');assert failure['error']=='Cell bank projected logical cap' and failure['stage']=='pass-a' and not failure['bankCapacityQualified']
receipt=failure['lastNativeReceipt'];assert not receipt['nativeEof'] and receipt['nodes']==receipt['visits']==1577373696
assert receipt['acceptedNodes']==1577373695 and receipt['ways']==receipt['relations']==receipt['pythonProjectionFrames']==0
assert receipt['witnessRows']==1505 and len(plan['queryIDs'])==1532 and receipt['semanticScope'].startswith('Complete only on success')
partial=load(raw/'pass-a/failure.json');assert partial['cellCodecRows']==4732121088 and partial['cellCodecCalls']==1155303
assert partial['fineView']['sourceBlocksCompared']==385101 and partial['fineView']['sourceShardsCompared']==752 and partial['fineView']['wholeFileVerificationPasses']==0
assert partial['fineView']['nodeRowsCompared']==1577373696 and partial['fineView']['payloadBytesRead']==28474117675
assert not (raw/'pass-b').exists() and not (raw/'result.json').exists() and not (raw/'pass-a/bank/index.json').exists()
metrics=load(raw/'metrics-end.json');cgroup=metrics['latest']['cgroup']
assert cgroup['memory.max']=='4294967296' and cgroup['memory.swap.max']=='0' and cgroup['memory.peak']=='4294967296'
assert 'oom 0' in cgroup['memory.events'] and 'oom_kill 0' in cgroup['memory.events']
assert metrics['retainedReservationBytes']==53324308583 and metrics['ownedLimitBytesExcludingTmp']==15126732697
summary=load(raw/'run-summary.json');assert summary['status']=='stopped' and summary['networkRequests']==0 and summary['hostSecondsIncludingBindingsAndCleanup']<14400
stop=load(folder/'cell-census-stop-v1.json');assert not stop['normalSourceEof'] and stop['completedSourcePasses']==0 and stop['newRetainedReservationBytes']==55406628967
if args.local_assets:
    root=repo/closed['root'];assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==set(closed['roster'])
    for name,row in closed['roster'].items():assert (root/name).stat().st_size==row['bytes'] and sha(root/name)==row['sha256'],name
print(json.dumps({'realBankCapStopPreserved':True,'recognizedNodeReceipts':1577373696,'completeSourcePasses':0,
                  'retainedPrefixFiles':31,'retainedPrefixBytes':2080277463,'workerAbsent':True,'oom':False,
                  'closedPrefixHashed':args.local_assets,'nationalPbfRead':False,'bankOrSourceInputQualified':False},indent=2))
