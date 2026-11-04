"""Portable complete national restriction-resolution proof; no large asset reads."""
import json
from verify_entry_native_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    record = load(HERE/'entry-resolution-run-closed-v1.json')
    root = HERE/'entry-resolution-run-raw-v1'
    for name, pin in record['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (root/name).stat().st_size == pin['bytes'] and sha(root/name) == pin['sha256']
    for name, pin in load(root/'execution-plan.json')['inputs'].items():
        if name.startswith(('scripts/', 'routing/', 'docs/')):
            assert sha(REPO/name) == pin
    report = load(root/'report.json')
    assert report['nativeCounts'] == [46533, 23009, 23387, 137, 149699, 99508, 22835, 9837326, 9703850]
    proof = report['independentAudit']
    assert proof['preArcsChecked'] == 9837326 and proof['decisionsChecked'] == 46533
    assert proof['fallbackUnionExact'] and proof['allPairsUseActualSourceNodeIdentity']
    assert not report['runtimeGraphBuilt'] and not report['appActivated']
    assert load(root/'run-summary.json')['exitCode'] == 0
    assert load(root/'cleanup.json')['independentInspectAbsent']
    state = load(root/'container-result.json')
    assert state['State']['ExitCode'] == state['clientExitCode'] == 0 and not state['State']['OOMKilled']
    metrics = load(root/'metrics.json')
    assert int(metrics['memory.peak']) == 658722816 and metrics['memory.swap.max'] == '0'
    assert 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
    return {**result, 'nationalEntryArcsResolved': True, 'nationalResolvedRules': 23009,
            'nationalPreEntryPairs': 22835, 'revisedDirectedArcCount': 9703850,
            'nationalGraphCorrectionBuilt': False, 'accuracyOrAppAccepted': False,
            'newUniqueClosedAllocationBytes': 2407149568, 'uniqueClosedRoots': 96}


if __name__ == '__main__':
    print(json.dumps(verify()))
