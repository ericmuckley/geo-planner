"""Verify saved controller qualification; no Docker/native/national source reads."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
import xml.etree.ElementTree as ET

folder=Path(__file__).resolve().parent;repo=folder.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_qualification_v8.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_full_extract_v1 import validate,isolation,output_ledger,proposal_for,CONTROL_CAPS
from coarse_osm_country_screen_v1 import MAX_VISITS
from coarse_osm_delta_v2 import Reader,ReferenceCodec
from coarse_osm_full_resources_v1 import OWNED_LIMIT,RETAINED,TMP,RETAINED_WORK_LIMIT

plan=load(folder/'full-plan-controls-v1.json');validate(plan)
freeze=load(folder/'full-freeze-controls-v1.json')
assert sha(folder/'full-plan-controls-v1.json')==freeze['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
closed=load(folder/'full-closed-controls-v1.json');raw=folder/'full-raw/controls-v1'
assert {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}==set(closed['roster'])
for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],name
assert closed['files']==len(closed['roster'])==24 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==112946
isolation(load(raw/'container-initial.json'))
result=load(raw/'container-result.json');assert result['State']['ExitCode']==result['clientExitCode']==0 and not result['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
assert load(folder/'full-cleanup-controls-v1.json')['independentAbsent']
controls=load(raw/'controls.json');assert controls=={'errors':0,'failures':0,'skips':0,'successful':True,'tests':14}
proposal=proposal_for(load(repo/plan['proposal']),'controls',CONTROL_CAPS)
assert proposal['proposedCaps']['scanObjectVisitsTotal']==2*MAX_VISITS and freeze['perCallVisitMaximum']==MAX_VISITS
state=load(raw/'extraction-result.json');receipts=state['nativeReceipts']
assert state['status']=='passed_all_highway_extraction_prototype' and state['independentAuditComplete']
assert state['scanObjectVisits']==18 and len(receipts)==2
for receipt in receipts:
    assert receipt['nativeEof'] and receipt['counts']=={'node':4,'way':3,'relation':2} and receipt['visits']==9
    assert receipt['semanticSha256']==plan['semantic'] and receipt['batchWays']==receipt['highwayWays']==2
    assert receipt['sourceIdentity']['sourceSha256']==plan['source']['sha256'] and receipt['postSourceHashBytes']==plan['source']['bytes']
assert state['liveBatchHeapLimitBytes']==134217728
source=load(raw/'host-source-binding.json');assert source['bytesRead']==plan['source']['bytes']==564 and source['sha256']==plan['source']['sha256'] and source['md5']==plan['source']['md5']
output=raw/'extract/elements.jsonl';assert sha(output)==state['outputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
assert output.read_bytes()==(folder/'qualification-raw/v8/controls/four-pass-reference/elements.jsonl').read_bytes()
assert output_ledger(output,proposal['windows'])==load(raw/'window-ledger.json')
assert state['retainedElements']==4 and state['windowOccurrences']==8
reader=Reader(raw/'extract/audit-index',ReferenceCodec())
expected={int(node.attrib['id']):[float(node.attrib['lon']),float(node.attrib['lat'])] for node in ET.parse(folder/'qualification-raw/v8/controls/full-fixture.osm').getroot().findall('node')}
try:assert reader.points(sorted(expected))==[expected[key] for key in sorted(expected)]
finally:reader.close()
assert not list((raw/'extract/primary-index').glob('[0-9]*.bin'))
result=load(raw/'result.json');assert result['status']=='passed_full_road_capture' and result['sourceObjects']==18
assert result['indexShardWrites']==2 and result['indexShardRemovals']==1 and result['indexWrittenBytes']==1370
assert result['codecCalls']==7 and result['codecDecodedRows']==28
assert not any(result[key] for key in ['nationalPhysicalIndexAllocated','sourceFeasibilityQualified','publisherBoundaryQualified','sourceAdapterImplemented','modelChanged'])
metrics=load(raw/'metrics-end.json');assert metrics['retainedReservationBytes']==RETAINED
assert metrics['observedWorkPeaks']['conservativeAllocatedBytes']<OWNED_LIMIT and OWNED_LIMIT+TMP+RETAINED==RETAINED_WORK_LIMIT
cgroup=metrics['latest']['cgroup'];assert cgroup['memory.max']=='4294967296' and cgroup['memory.swap.max']=='0'
assert int(cgroup['memory.peak'])==48480256 and 'oom_kill 0' in cgroup['memory.events']
assert load(raw/'run-summary.json')['status']=='passed_full_road_capture'
print(json.dumps({'fullControllerQualified':True,'linuxTests':14,'skips':0,'twoPassObjects':18,'allIndexCoordinates':4,
                  'exactIndependentOutput':True,'aggregateNationalBudgetExercised':True,'workerAbsent':True,
                  'nationalSourceRead':False,'nationalIndexAllocated':False},indent=2))
