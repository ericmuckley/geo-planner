"""Saved selected-element cap stop; no native, PBF or ignored-payload reads."""
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
    for name in ('verify_cell_census_run_v2.py','verify_filtered_capture_controls_v1.py'):
        subprocess.run([sys.executable,'-B',str(REPORT/name)],check=True,stdout=subprocess.DEVNULL)
    sys.path.insert(0,str(REPO/'scripts'))
    from run_osm_filtered_capture_v1 import validate,isolation
    plan=load(REPORT/'filtered-capture-plan-run-v1.json');validate(plan)
    freeze=load(REPORT/'filtered-capture-freeze-run-v1.json');assert sha(REPO/freeze['recipe'])==freeze['sha256']
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','docs/evidence/')):assert sha(REPO/name)==pin,name
    closed=load(REPORT/'filtered-capture-closed-run-v1.json');raw=REPORT/'filtered-capture-raw/run-v1'
    assert closed['closerSha256']==sha(REPO/'scripts/close_osm_filtered_stop_v1.py')
    assert closed['files']==62 and closed['bytes']==938722550
    assert {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}=={name for name,r in closed['roster'].items() if not r['ignoredPart']}
    for name,pin in closed['roster'].items():
        if not pin['ignoredPart']:assert (raw/name).stat().st_size==pin['bytes'] and sha(raw/name)==pin['sha256'],name
    isolation(load(raw/'container-initial.json'));end=load(raw/'container-result.json')
    assert end['State']['ExitCode']==end['clientExitCode']==2 and not end['State']['OOMKilled']
    assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
    absence=load(REPORT/'filtered-capture-cleanup-run-v1.json');assert absence['independentlyAbsent'] and absence['queryReturnCode']==0 and absence['containerIds']==[]
    state=load(raw/'extraction-result.json');failure=load(raw/'worker-failure.json');receipt=failure['lastNativeReceipt']
    assert state['status']=='stopped' and state['error']=='Selected unique element cap' and not state['independentAuditComplete']
    assert receipt['counts']=={'node':1606229364,'way':11201886} and not receipt['nativeEof'] and receipt['acceptedWays']==11201885
    assert receipt['batchWays']==10736397 and receipt['batchReferences']==170361375
    assert state['extractBytes']==state['retainedElements']==0 and not (raw/'extract/elements.jsonl').exists() and not (raw/'result.json').exists()
    assert not (raw/'extract/primary-index').exists() and not (raw/'extract/audit-index').exists()
    bank=raw/'extract/all-highway-primary-selection-cells';reference=REPORT/'cell-census-raw/run-v2/pass-a/bank'
    assert (bank/'index.json').read_bytes()==(reference/'index.json').read_bytes() and (bank/'directory.bin').read_bytes()==(reference/'directory.bin').read_bytes()
    manifest=load(bank/'index.json')
    for i,part in enumerate(manifest['parts']):
        pin=closed['roster'][f'extract/all-highway-primary-selection-cells/{i:04d}.bin']
        assert pin['ignoredPart'] and pin['bytes']==part['bytes'] and pin['sha256']==part['sha256']
    metrics=load(raw/'metrics-end.json');assert int(metrics['latest']['cgroup']['memory.peak'])==4294967296 and 'oom_kill 0' in metrics['latest']['cgroup']['memory.events']
    stop=load(REPORT/'filtered-capture-stop-v1.json');assert stop['status']=='stopped_selected_unique_cap' and stop['selectedUniqueCap']==250000 and not stop['wholeRoadCaptureQualified'] and not stop['modelChanged']
    print(json.dumps({'selectedCapStopPreserved':True,'sourceNodes':1606229364,'sourceWays':11201886,'sourceEof':False,'outputBytes':0,'workerAbsent':True,'nationalCaptureQualified':False,'modelChanged':False}))


if __name__=='__main__':main()
