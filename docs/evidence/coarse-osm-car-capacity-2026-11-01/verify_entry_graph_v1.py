"""Portable corrected graph, independent source/superset and memory proof."""
import json
from verify_entry_resolution_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def stage(operation):
    record = load(HERE/f'entry-graph-{operation}-closed-v1.json')
    root = HERE/f'entry-graph-{operation}-raw-v1'
    for name, pin in record['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (root/name).stat().st_size == pin['bytes'] and sha(root/name) == pin['sha256']
    for name, pin in load(root/'execution-plan.json')['inputs'].items():
        if name.startswith(('scripts/', 'routing/', 'docs/')):
            assert sha(REPO/name) == pin
    assert load(root/'cleanup.json')['independentInspectAbsent']
    assert load(root/'run-summary.json')['exitCode'] == 0
    final = load(root/'container-result.json')
    assert final['State']['ExitCode'] == final['clientExitCode'] == 0 and not final['State']['OOMKilled']
    metrics = load(root/'metrics.json')
    assert int(metrics['memory.peak']) <= 4294967296 and metrics['memory.swap.max'] == '0'
    assert 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
    return load(root/'report.json')


def verify():
    result = previous()
    assert stage('controls')['controls'] == {'tests': 21, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    report = stage('run')
    assert report['finalPayloadBytes'] == 128500793
    assert report['augmentationCounts'] == [22835, 231508, 19496, 3339, 249140, 9703850]
    proof = report['independentAudit']
    assert proof['baseFields']['directedCostsAndPhysicalReversesChecked'] == 9703850
    assert proof['baseFields']['sourceTurnRecordsChecked'] == 409178
    assert proof['oldDirectedArcsRetained'] == 9620680 and proof['reopenedDirectedArcs'] == 83170
    assert proof['oldAllowedTransitionsPreserved'] and proof['newEntryPairsOnlyTouchOriginallyClosedArcs']
    assert proof['nativeLibraryExecutions'] == 0 and not report['appActivated']
    assert not report['spatialOrPaidGeometryOrCodecBuilt']
    controls = load(HERE/'access-field-v2-controls.json')
    assert controls['tests'] == 7 and controls['independentSourceMinima'] == 9600 and controls['countrySizedReleaseIterations'] == 12
    assert sha(HERE/controls['transcript']) == controls['transcriptSha256']
    for name, pin in controls['bindings'].items():
        assert sha(REPO/name) == pin
    assert controls['resolvedGraphConservativeSearchBackingBytes'] == 59089419 < controls['scratchLimitBytes'] == 67108864
    return {**result, 'nationalGraphCorrectionBuilt': True, 'allOldAllowedTransitionsPreserved': True,
            'reopenedDirectedArcs': 83170, 'finalNationalForbiddenPairs': 249140,
            'nationalSpatialGeometryOrAccuracyAccepted': False, 'accuracyOrAppAccepted': False,
            'newUniqueClosedAllocationBytes': 2539778048, 'uniqueClosedRoots': 98,
            'sameMathBorrowedHeapControls': 7}


if __name__ == '__main__':
    print(json.dumps(verify()))
