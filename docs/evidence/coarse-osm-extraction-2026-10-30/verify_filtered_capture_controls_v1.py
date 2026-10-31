"""Saved complete tiny filtered-capture controller proof, without native execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPORT=Path(__file__).resolve().parent
REPO=REPORT.parents[2]


def load(path):return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    subprocess.run([sys.executable,'-B',str(REPORT/'verify_cell_census_controls_v2.py')],check=True,stdout=subprocess.DEVNULL)
    sys.path.insert(0,str(REPO/'scripts'))
    from run_osm_filtered_capture_v1 import validate,isolation,check_receipt
    from coarse_osm_capture_resources_v1 import RETAINED,OWNED_LIMIT,TMP,CENSUS_RESERVATION
    plan=load(REPORT/'filtered-capture-plan-controls-v1.json');validate(plan)
    freeze=load(REPORT/'filtered-capture-freeze-controls-v1.json');assert sha(REPO/freeze['recipe'])==freeze['sha256']
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','docs/evidence/')):assert sha(REPO/name)==pin,name
    closed=load(REPORT/'filtered-capture-closed-controls-v1.json');raw=REPORT/'filtered-capture-raw/controls-v1'
    assert {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}==set(closed['roster'])
    for name,pin in closed['roster'].items():assert (raw/name).stat().st_size==pin['bytes'] and sha(raw/name)==pin['sha256'],name
    isolation(load(raw/'container-initial.json'))
    result=load(raw/'container-result.json');assert result['State']['ExitCode']==result['clientExitCode']==0 and not result['State']['OOMKilled']
    assert load(raw/'cleanup.json')['removed'] and load(REPORT/'filtered-capture-cleanup-controls-v1.json')['independentlyAbsent']
    assert load(raw/'controls.json')=={'errors':0,'failures':0,'skips':0,'successful':True,'tests':13}
    output=raw/'extract/elements.jsonl';assert output.stat().st_size==1470 and sha(output)=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
    reference=REPORT/'qualification-raw/v13/controls/readonly-filtered-prototype/elements.jsonl';assert output.read_bytes()==reference.read_bytes()
    state=load(raw/'extraction-result.json');assert state['status']=='passed_cell_filtered_extraction_prototype' and state['independentAuditComplete']
    assert state['retainedElements']==4 and state['windowOccurrences']==8 and state['scanObjectVisits']==18
    for receipt in state['nativeReceipts']:check_receipt(receipt,plan)
    assert len(state['nativeReceipts'])==2 and len(state['coarseLookups'])==2
    for row in state['coarseLookups']:assert row['examinedReferences']==4 and row['fineReferences']==2 and row['certifiedOutsideWays']==1 and row['bankBytes']==581
    fine=load(raw/'fine-revalidation.json');assert len(fine)==2
    for row in fine:assert row['readOnly'] and row['nodeRowsCompared']==4 and row['sourceBlocksCompared']==row['sourceShardsCompared']==row['wholeFileVerificationPasses']==1 and row['payloadBytesRead']==681
    assert not (raw/'extract/primary-index').exists() and not (raw/'extract/audit-index').exists()
    result=load(raw/'result.json');assert result['status']=='passed_full_road_capture' and result['sourcePasses']==2 and result['sourceObjects']==18
    assert result['readOnlyFineInputRevalidatedForThisStage'] and result['cellCodecRows']==40 and result['cellCodecCalls']==10 and result['maskReferences']==8 and result['maskCalls']==2
    assert not any(result[k] for k in ('nationalRawAcquiredFileCaptureComplete','nationalPhysicalIndexAllocated','publisherBoundaryQualified','sourceAdapterImplemented','sourceFeasibilityQualified','modelChanged'))
    metrics=load(raw/'metrics-end.json');assert metrics['retainedReservationBytes']==RETAINED==59768705127
    assert RETAINED+OWNED_LIMIT+TMP==64*1024**3 and CENSUS_RESERVATION==4*1024**3+64*1024**2
    assert int(metrics['latest']['cgroup']['memory.peak'])<=4294967296 and 'oom_kill 0' in metrics['latest']['cgroup']['memory.events']
    print(json.dumps({'filteredCaptureControllerTinyQualified':True,'linuxTests':13,'skips':0,'sourceObjects':18,'fourPassOutputExact':True,'noFineIndexCopiesOrDeletion':True,'workerAbsent':True,'nationalCaptureQualified':False}))


if __name__=='__main__':main()
