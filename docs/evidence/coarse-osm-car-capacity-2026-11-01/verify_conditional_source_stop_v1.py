"""Preserve the final metadata-audit access-time stop; no replay/admission."""
import json
from verify_conditional_census_controls_v1 import verify as previous
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();closed=load(HERE/'conditional-source-run-closed-v1.json');root=HERE/'conditional-source-run-raw-v1'
    assert closed['terminalRecord']=='failure.json'
    for name,pin in closed['roster'].items():
        if not pin['ignoredLargeAsset']:assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    for name,pin in load(root/'execution-plan.json')['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    assert load(root/'failure.json')['error']=="PilotError('Changed record bytes/stat stable')"
    assert load(root/'cleanup.json')['independentInspectAbsent'] and load(root/'run-summary.json')['exitCode']==2
    final=load(root/'container-result.json');assert final['State']['ExitCode']==final['clientExitCode']==1 and not final['State']['OOMKilled']
    metrics=load(root/'metrics.json');assert metrics['memory.swap.max']=='0' and 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
    assert 'receipt.json' not in closed['roster'] and 'source-census.json' not in closed['roster']
    allocation=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes'];assert allocation==5412712448
    return {**result,'conditionalNationalV1FinalTagAuditStopped':True,'conditionalNationalV1SourceReceiptRetained':False,
            'conditionalNationalMetadataMeasured':False,'uniqueClosedRoots':177,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
