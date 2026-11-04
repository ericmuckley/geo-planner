"""Saved 1GiB OOM stop proof; optional derived partial-output hash audit only."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2]
load=lambda p:json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_continuous_match_controls_v1.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
from run_osm_continuous_match_v1 import validate,isolation
plan=load(folder/'continuous-match-plan-run-v1.json');validate(plan);freeze=load(folder/'continuous-match-freeze-run-v1.json');assert sha(folder/'continuous-match-plan-run-v1.json')==freeze['recipeSha256']=='91538f9f64af5766d734c2ddf393497f045119b467a767bcecec319b20401d42'
for path,pin in plan['inputs'].items():
    if not path.startswith('data/'):assert sha(repo/path)==pin
for path,pin in freeze['newProducerFiles'].items():assert sha(repo/path)==pin
closed=load(folder/'continuous-match-closed-run-v1.json');raw=folder/'continuous-match-raw/run-v1';assert closed['files']==len(closed['roster'])==23 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==75606743
for name,row in closed['roster'].items():
    path=(repo/closed['root'] if row['ignoredLargeAsset'] else raw)/name
    if not row['ignoredLargeAsset'] or args.local_assets:assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
assert closed['closerSha256']==sha(repo/'scripts/close_osm_continuous_match_v1.py')
isolation(load(raw/'container-initial.json'));state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==137 and state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent'] and load(folder/'continuous-match-cleanup-run-v1.json')['independentlyAbsent']
run=load(raw/'run-summary.json');assert run['exitCode']==2 and run['networkRequests']==run['pbfOrNativeHelperReads']==0
assert not any(name in closed['roster'] for name in ('report.json','result.json','metrics.json'))
receipt=load(raw/'node-receipt.json');assert receipt['sha256']=='efc36dc058b198711cc2666a751c9fd60b52d37902efbb22e1cba8b5f30f91f4' and receipt['types']=={'node':1123919,'relation':4900,'way':239253}
reports=[name for name in closed['roster'] if name.startswith('windows/') and name.endswith('/report.json')];assert reports==[f'windows/origin-{i:02d}/report.json' for i in range(4)]
print(json.dumps({'status':'preserved_1GiB_OOM_stop','completeWindows':4,'completeActualRun':False,'workerAndClientExit':137,'oomKilled':True,'workerAbsent':True,'newDerivedPartialFilesHashed':args.local_assets,'usableLimitOrMatchingQualified':False,'modelChanged':False},indent=2))
