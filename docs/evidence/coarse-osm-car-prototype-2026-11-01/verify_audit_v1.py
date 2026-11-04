"""Portable completed car prototype proof. No ignored assets or worker replay."""
import hashlib,importlib.util,json
from pathlib import Path

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def verify():
    spec=importlib.util.spec_from_file_location('car_control_proof',HERE/'verify_controls_v1.py');controls=importlib.util.module_from_spec(spec);spec.loader.exec_module(controls);assert controls.verify()['qualified']
    for stage in ('run','audit'):
        closed=load(HERE/f'car-closed-{stage}-v1.json');root=HERE/f'car-raw/{stage}-v1'
        for name,pin in closed['roster'].items():
            if pin['ignoredLargeAsset']:continue
            p=root/name;assert p.is_file() and p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],name
        assert load(HERE/f'car-cleanup-{stage}-v1.json')['independentlyAbsent'] and load(root/'cleanup.json')['independentInspectAbsent']
        plan=load(root/'execution-plan.json');freeze=load(HERE/('freeze-run-v1.json' if stage=='run' else 'audit-freeze-v1.json'));assert sha(root/'execution-plan.json')==freeze['recipeSha256']
        bindings={name:pin for name,pin in (plan['inputs']|plan['hostBindings']).items() if name.startswith(('scripts/','routing/'))} if stage=='run' else plan['hostFiles']
        for name,pin in bindings.items():assert sha(REPO/name)==pin,name
        final=load(root/'container-result.json');assert final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled']
        metrics=load(root/'metrics.json');events=dict(line.split() for line in metrics['memory.events'].splitlines());assert metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and int(metrics['memory.peak'])<=2147483648 and events['oom']==events['oom_kill']=='0'
        summary=load(root/'run-summary.json');assert summary['exitCode']==summary['networkRequests']==0 and not summary['modelChanged']
        initial=load(root/'container-initial.json');host=initial['HostConfig'];assert host['Memory']==host['MemorySwap']==2147483648 and host['NetworkMode']=='none' and host['ReadonlyRootfs'] and host['NanoCpus']==1000000000
        assert all(not m['RW'] for m in initial['Mounts'] if m['Destination']!='/work')
    root=HERE/'car-raw/run-v1';report=load(root/'report.json');artifacts=load(root/'artifacts.json');closed=load(HERE/'car-closed-run-v1.json');result=load(root/'result.json')
    assert result['reportSha256']==sha(root/'report.json') and result['artifactsSha256']==sha(root/'artifacts.json')
    for name,pin in artifacts.items():assert closed['roster'][name]['sha256']==pin['sha256'] and closed['roster'][name]['bytes']==pin['bytes']
    assert sum(pin['bytes'] for pin in artifacts.values())==report['payload']['payloadBytes']==1321511
    assert (report['selectedWays'],report['selectedNativeNodes'],report['rawArcs'],report['contractedArcs'])==(28995,143560,218666,86517)
    assert report['payload']['vertices']==53672 and report['payload']['costOverflowEntries']==report['payload']['reverseOverflowEntries']==0 and report['payload']['forbiddenTurnPairs']==2269
    assert report['allNativePointAliases']==89888 and report['policy']['ferries']=='excluded'
    assert not any(report[k] for k in ('etaQualified','nationalArtifactBuilt','vercelQualified','modelChanged'))
    qs=report['queries'];assert len(qs)==82 and len({q['windowId'] for q in qs})==21 and sum(q['reverseOfOriginal'] for q in qs)==41
    finite=[]
    for q in qs:
        a,b,c=q['raw'],q['contracted'],q['quantized'];assert a['costMs']==b['costMs'] and c['costMs']==q['binaryQuantizedMs']
        if a['costMs'] is None:assert c['costMs'] is None
        else:assert b['costMs']<=c['costMs']<=b['costMs']+124*b['fragments'];finite.append(q)
    assert len(finite)==68 and sum(q['internalEndpoints'] for q in qs)==16
    audit=load(HERE/'car-raw/audit-v1/audit.json');assert audit['status']=='independent_source_static_car_audit_passed' and audit['auditorSha256']==sha(HERE/'audit_v1.py') and audit['reportSha256']==sha(root/'report.json') and audit['closedSha256']==sha(HERE/'car-closed-run-v1.json')
    for key,expected in {'sourceWaysChecked':28995,'sourceNativeNodesChecked':143560,'sourceRelationsChecked':4900,'rawArcsChecked':218666,'contractedArcCostsAndReverseIdentitiesChecked':86517,'nodeFlagsChecked':53672,'forbiddenTurnPairsChecked':2269,'originalPairsChecked':41,'directionalQueriesChecked':82}.items():assert audit[key]==expected,key
    assert audit['selfTests']=={'checks':8,'successful':True} and not any(audit[k] for k in ('sourcePbfReads','networkRequests','applicationDbReads','etaQualified','nationalArtifactBuilt','vercelQualified','modelChanged'))
    return {'qualifiedCapturedCarEncoding':True,'linuxTests':26,'directionalChecks':82,'finite':68,'unreachableRetained':14,'independentlyCheckedCompactArcs':86517,'isolatedPayloadBytes':1321511,'workersIndependentlyAbsent':True,'reads':'Repository code, frozen plans and small mirrored results only. No ignored graph/SQLite/PBF/tool assets.'}
if __name__=='__main__':print(json.dumps(verify()))
