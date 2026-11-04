"""Portable closed reachability diagnosis proof; no data/worker replay."""
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_bytes())
def verify():
    root=HERE/'car-raw/reachability-v1';closed=load(HERE/'car-closed-reachability-v1.json')
    for name,pin in closed['roster'].items():
        assert not pin['ignoredLargeAsset'];path=root/name
        assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256'],name
    plan=load(root/'execution-plan.json');assert sha(root/'execution-plan.json')==load(HERE/'reachability-freeze-v2.json')['recipeSha256']
    for name,pin in plan['hostFiles'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    tested=load(root/'controls.json');assert tested=={'tests':8,'successful':True,'failures':0,'errors':0,'skips':0}
    report=load(root/'diagnosis.json');assert report['diagnosticOnly'] and not any(report[k] for k in ('modelChanged','etaQualified','networkRequests','applicationDbReads','sourcePbfReads'))
    assert report['diagnoserSha256']==sha(REPO/'scripts/coarse_osm_car_reachability_v1.py')
    cases=report['cases'];assert len(cases)==14 and len({c['originalDirectionalIndex'] for c in cases})==14 and report['counts']['baselineChecks']==82
    original=load(HERE/'car-raw/run-v1/report.json')['queries']
    for c in cases:
        q=original[c['originalDirectionalIndex']];assert q['raw']['costMs'] is None and q['sourceNodeIds']==c['sourceNodeIds'] and q['windowId']==c['windowId']
        assert c['counterfactuals']['geometry-only']['reachable']
        assert set(c['counterfactuals'])==set(plan['modes'])-{'baseline'}
    expected={'without-unsupported-closures':10,'without-direction-limits':6,'without-way-exclusions':3,'without-supported-turns':2,'without-blocked-controls':0,'geometry-only':14}
    for mode,count in expected.items():assert sum(c['counterfactuals'][mode]['reachable'] for c in cases)==count
    assert report['counts'].get('restored:without-blocked-controls',0)==0
    metrics=load(root/'metrics.json');events=dict(line.split() for line in metrics['memory.events'].splitlines());assert metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and events['oom']==events['oom_kill']=='0'
    final=load(root/'container-result.json');assert final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled']
    assert load(root/'cleanup.json')['independentInspectAbsent'] and load(HERE/'car-cleanup-reachability-v1.json')['independentlyAbsent']
    assert load(root/'run-summary.json')['exitCode']==0
    return {'qualifiedDiagnosis':True,'baselineChecks':82,'unreachableRetained':14,'counterfactualRestorations':expected,'interpretation':'Overlapping diagnostic effects; no relaxed permission or outside-capture detour admission.','workerAbsent':True}
if __name__=='__main__':print(json.dumps(verify()))
