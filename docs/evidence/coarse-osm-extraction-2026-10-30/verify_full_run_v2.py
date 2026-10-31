"""Saved national-run proof. --local-assets hashes only the closed derived files."""
import argparse
from collections import Counter
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
folder=Path(__file__).resolve().parent;repo=folder.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_full_controls_v2.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_full_extract_v2 import validate,isolation,proposal_for,RUN_CAPS,SOURCE,MAX_VISITS
from coarse_osm_full_resources_v1 import OWNED_LIMIT,RETAINED,TMP,RETAINED_WORK_LIMIT
from coarse_osm_records import canonical,normalize,strict_json
from coarse_osm_bulk_audit import crossing

plan=load(folder/'full-plan-run-v2.json');validate(plan)
freeze=load(folder/'full-freeze-run-v2.json');assert sha(folder/'full-plan-run-v2.json')==freeze['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
closed=load(folder/'full-closed-run-v2.json');raw=folder/'full-raw/run-v2'
assert closed['workerIndependentlyAbsent'] and load(folder/'full-cleanup-run-v2.json')['independentAbsent']
assert closed['files']==len(closed['roster']) and closed['bytes']==sum(row['bytes'] for row in closed['roster'].values())
mirrored={name for name,row in closed['roster'].items() if not row['ignoredPayload']}
assert {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}==mirrored
catalog=load(repo/plan['catalog'])
for name,row in closed['roster'].items():
    if row['ignoredPayload']:
        assert Path(name).parent.as_posix() in ('extract/primary-index','extract/audit-index') and Path(name).suffix=='.bin'
        expected=catalog['shards'][int(Path(name).stem)]
        assert row['bytes']==expected['bytes'] and row['sha256']==expected['sha256'],name
    else:assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],name
isolation(load(raw/'container-initial.json'))
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
binding=load(raw/'host-source-binding.json')
assert binding['bytesRead']==SOURCE['bytes'] and binding['sha256']==SOURCE['sha256'] and binding['md5']==SOURCE['md5']
assert binding['seconds']<RUN_CAPS['hashSeconds']
summary=load(raw/'run-summary.json');assert summary['hostSecondsIncludingBindingsAndCleanup']<14400 and summary['networkRequests']==0 and not summary['modelChanged']
assert closed['conservativeAllocatedBytes']<OWNED_LIMIT and OWNED_LIMIT+RETAINED+TMP==RETAINED_WORK_LIMIT
if (raw/'container-result.json').exists():final=load(raw/'container-result.json')
else:final=load(raw/'container-error-final.json')
assert not final['State']['Running']
state=load(raw/'extract/state.json') if (raw/'extract/state.json').exists() else None
success=summary['status']=='passed_full_road_capture'
if success:
    assert final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled']
    result=load(raw/'result.json');assert result['rawAcquiredFileCaptureComplete'] and result['nationalPhysicalIndexAllocated']
    assert result['sourcePasses']==2 and result['sourceObjects']==2*MAX_VISITS and state['independentAuditComplete']
    assert not any(result[k] for k in ['sourceFeasibilityQualified','publisherBoundaryQualified','sourceAdapterImplemented','modelChanged'])
    assert state['status']=='passed_all_highway_extraction_prototype' and len(state['nativeReceipts'])==2
    for receipt in state['nativeReceipts']:
        assert receipt['nativeEof'] and receipt['counts']==SOURCE['counts'] and receipt['visits']==MAX_VISITS
        assert receipt['semanticSha256']==plan['semantic'] and receipt['batchWays']==receipt['highwayWays']==52053199
        assert receipt['sourceIdentity']['sourceSha256']==SOURCE['sha256'] and receipt['sourceIdentity']['sourceMd5']==SOURCE['md5']
        assert receipt['postSourceHashBytes']==SOURCE['bytes']
    assert result['codecDecodedRows']<=RUN_CAPS['codecRows'] and result['codecCalls']<=RUN_CAPS['codecCalls']
    assert all(item['authenticatedShardBytes']<=RUN_CAPS['lookupBytesPerPass'] for item in state['lookups'])
    assert result['indexShardWrites']==1532 and result['indexShardRemovals']==766
    assert not any(name.startswith('extract/primary-index/') and row['ignoredPayload'] for name,row in closed['roster'].items())
    assert sum(row['ignoredPayload'] for row in closed['roster'].values())==766
    assert load(raw/'extract/audit-index/index.json')==catalog
    metrics=load(raw/'metrics-end.json');cgroup=metrics['latest']['cgroup']
    assert cgroup['memory.max']=='4294967296' and cgroup['memory.swap.max']=='0' and int(cgroup['memory.peak'])<=4294967296
    assert 'oom_kill 0' in cgroup['memory.events']
    assert metrics['observedWorkPeaks']['conservativeAllocatedBytes']<OWNED_LIMIT
    proposal=proposal_for(load(repo/plan['proposal']),'run',RUN_CAPS);windows=proposal['windows'];snapshot=SOURCE['publisherState']
    output=raw/'extract/elements.jsonl';assert output.stat().st_size<=134217728 and sha(output)==state['outputSha256']
    objects={};members={window['id']:set() for window in windows};rows={}
    with output.open('rb') as stream:
        for line in stream:
            assert len(line)<=1048576
            row=strict_json(line);element=row['element'];key=element['type'],element['id']
            assert key not in objects and canonical(normalize(element,snapshot,1048576))==canonical(element)
            assert row['publisherStateUtc']==snapshot and row['elementSha256']==hashlib.sha256(canonical(element)).hexdigest()
            assert row['windowIds'] and len(set(row['windowIds']))==len(row['windowIds']) and set(row['windowIds'])<=set(members)
            assert row['windowIds']==[window['id'] for window in windows if window['id'] in row['windowIds']]
            objects[key]=element;rows[key]=row
            for window in row['windowIds']:members[window].add(key)
    assert len(objects)==state['retainedElements']<=250000
    needed=set();expected_members={window['id']:set() for window in windows}
    for key,element in objects.items():
        if key[0]!='way':continue
        nodes=[objects['node',identity] for identity in element['nodes']];needed.update(element['nodes'])
        assert rows[key]['geometryDependencySha256']==hashlib.sha256(canonical([snapshot,nodes])).hexdigest()
        points=[[node['lon'],node['lat']] for node in nodes]
        for window in windows:
            if crossing(points,window['bbox']):
                expected_members[window['id']].add(key)
                expected_members[window['id']].update(('node',identity) for identity in element['nodes'])
    assert needed=={identity for kind,identity in objects if kind=='node'}
    for key,element in objects.items():
        if key[0]=='relation':
            for values in expected_members.values():
                if any(member['type'] in ('node','way') and (member['type'],member['ref']) in values for member in element['members']):values.add(key)
    assert expected_members==members
    ledger=load(raw/'window-ledger.json');assert len(ledger['windows'])==21 and ledger['uniqueElements']==len(objects)
    assert ledger['uniqueCounts']==dict(Counter(key[0] for key in objects))
    assert ledger['windowOccurrences']==state['windowOccurrences']==sum(map(len,members.values()))<=500000
    for row in ledger['windows']:
        values=members[row['id']]
        assert row['status']=='complete_from_acquired_file_only' and row['counts']==dict(Counter(key[0] for key in values)) and row['elements']==len(values)
else:
    assert summary['status']=='stopped'
    assert (raw/'driver-failure.json').exists() or (raw/'worker-failure.json').exists()
    assert not (raw/'result.json').exists()
    if state is not None:assert state['status']!='passed_all_highway_extraction_prototype' or not (raw/'window-ledger.json').exists()
if args.local_assets:
    root=repo/closed['root']
    assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==set(closed['roster'])
    for name,row in closed['roster'].items():assert (root/name).stat().st_size==row['bytes'] and sha(root/name)==row['sha256'],name
print(json.dumps({'nationalRawCapturePassed':success,'closedFiles':closed['files'],'closedBytes':closed['bytes'],
                  'independentlyAbsent':True,'closedDerivedAssetsHashed':args.local_assets,'nationalSourceRead':False,
                  'sourceSuitabilityOrModelAdmission':False},indent=2))
