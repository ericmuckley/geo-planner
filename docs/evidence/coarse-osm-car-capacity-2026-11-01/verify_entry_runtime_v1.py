"""Portable new spatial/paid geometry/storage chain; no ignored asset reads."""
import json
from verify_entry_graph_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def stage(prefix, native=False):
    record = load(HERE/f'{prefix}-closed-v1.json')
    root = HERE/f'{prefix}-raw-v1'
    for name, pin in record['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (root/name).stat().st_size == pin['bytes'] and sha(root/name) == pin['sha256']
    plan = load(root/'execution-plan.json')
    for name, pin in plan.get('inputs', plan.get('bindings', {})).items():
        if name.startswith(('scripts/', 'routing/', 'docs/')):
            assert sha(REPO/name) == pin
    assert record['terminalRecord'] == 'report.json'
    if native:
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
    assert stage('entry-derived-controls', True)['controls'] == {'tests': 30, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    spatial = stage('entry-derived-spatial', True)
    assert spatial['nativeResult']['arcs'] == spatial['independentAudit']['directedArcsCostsPhysicalReversesChecked'] == 9703850
    assert spatial['independentAudit']['forbiddenTurnPairsChecked'] == 249140
    geometry = stage('entry-derived-geometry', True)
    proof = geometry['independentAudit']
    assert proof['physicalSpansChecked'] == 6482393 and proof['directedSourceCostsChecked'] == 9703850
    assert proof['interiorPositionsChecked'] == 690628 and proof['longSpansChecked'] == 529459
    assert proof['runtimeBytes'] == geometry['nativeResult']['runtimeBytes'] == 11473727
    totals = []
    for kind, fields, raw, compressed in [('core', 13, 128842616, 46048840), ('geometry', 7, 11473727, 7898308)]:
        encoded = stage('entry-codec-'+kind)
        audited = stage('entry-codec-audit-'+kind)
        assert encoded['fields'] == audited['fields'] == fields
        assert encoded['rawBytes'] == audited['bytesIndependentlyDecodedAndCompared'] == raw
        assert encoded['compressedBytes'] == audited['compressedBytes'] == compressed
        assert audited['nativeProducerExecutions'] == audited['routingQueries'] == 0
        totals.append(compressed)
    stopped = load(HERE/'entry-derived-spatial-preinput-stop-v1.json')
    assert not stopped['workerCreated'] and not stopped['sourceOrGraphInputsRead'] and not stopped['recipeChanged']
    return {**result, 'newSpatialAndPaidGeometryIndependentlyAudited': True,
            'newRuntimeStorageAllBytesIndependentlyCompared': 140316343,
            'newCoreAndGeometryCompressedBytes': sum(totals),
            'newUniqueClosedAllocationBytes': 2820444160, 'uniqueClosedRoots': 105,
            'newActualLoaderQueriesOrAccuracyMeasured': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
