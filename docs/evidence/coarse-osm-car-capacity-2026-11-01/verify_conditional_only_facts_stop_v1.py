"""Preserve the national flag-order guard stop; never treat it as success."""
import json
from verify_conditional_only_facts_capture_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    prefix = 'conditional-only-facts-run'
    closed = load(HERE / (prefix + '-closed-v1.json'))
    root = HERE / (prefix + '-raw-v1')
    assert closed['terminalRecord'] == 'failure.json'
    for name, pin in closed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (root/name).stat().st_size == pin['bytes'] and sha(root/name) == pin['sha256']
    plan = load(root/'execution-plan.json')
    for name, pin in plan['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')): assert sha(REPO/name) == pin
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 423
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    assert load(root/'failure.json')['error'] == "PilotError('Only already-qualified incomplete-node changes differ from prior passable flags')"
    assert load(root/'cleanup.json')['removed'] and load(root/'cleanup.json')['independentInspectAbsent']
    assert load(root/'run-summary.json')['exitCode'] == 2
    final = load(root/'container-result.json')
    assert final['State']['ExitCode'] == final['clientExitCode'] == 1 and not final['State']['OOMKilled']
    metrics = load(root/'metrics.json')
    assert int(metrics['memory.peak']) < 4294967296 and metrics['memory.swap.max'] == '0'
    assert 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
    assert not (root/'report.json').exists()
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert 64500000000 + total + 104857600 < 72*1024**3
    return {**result,'status':'national_mandatory_facts_v1_flag_order_guard_stop_preserved',
            'registeredClosedRoots':424,'newUniqueClosedAllocationBytes':total,
            'conditionalOnlyNationalFactsQualified':False,'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))
