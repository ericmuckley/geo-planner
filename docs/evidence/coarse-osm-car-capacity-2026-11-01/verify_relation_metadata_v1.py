"""Portable complete relation-metadata parity proof; no PBF or graph replay."""
import json
from verify_preparation_v1 import HERE, REPO, load, sha
from verify_relation_metadata_controls_v1 import verify as controls


def verify():
    result = controls()
    closed = load(HERE/'relation-metadata-run-v2-closed-v1.json')
    root = HERE/'relation-metadata-run-v2-raw-v1'
    assert closed['terminalRecord'] == 'report.json'
    for name, pin in closed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (root/name).stat().st_size == pin['bytes'] and sha(root/name) == pin['sha256']
    plan = load(root/'execution-plan.json')
    for name, pin in plan['bindings'].items():
        assert sha(REPO/name) == pin
    report = load(root/'report.json')
    assert report['status'] == 'complete_national_relation_metadata_parity_passed'
    assert report['scan'] == {'relations': 1624265, 'restrictionRecordsSelected': 480203, 'headersVisited': 221321,
                             'compressedTailBytes': 268479971, 'decodedTailBytes': 835465185,
                             'earlierNodeWayBodiesValidated': False, 'nodeWayObjectsProjected': 0}
    p = report['parity']
    assert (p['supportedSourceTurnsMatched'], p['unsupportedRelationsRetained'], p['closureWayIdsMatched'], p['unlocatableSourceRecordsMatched']) == (409178, 70376, 149699, 2)
    asset = closed['roster']['unsupported-relations.jsonl']
    assert asset['sha256'] == p['selectedMetadataSha256'] == '2929a9c5febd79bec88da4b2f8bbe4b6fc9bab1bc9229047e60ed4a7fabda332'
    assert asset['bytes'] == p['selectedMetadataBytes'] == 21119251
    before, after = load(root/'source-before.json'), load(root/'source-after.json')
    assert before['sha256'] == after['sha256'] == plan['source']['sha256']
    assert before['md5'] == after['md5'] == plan['source']['md5']
    assert before['bytes'] == after['bytes'] == 12229320016 and before['stat'] == after['stat']
    metrics, cleanup = load(root/'metrics.json'), load(root/'cleanup.json')
    assert metrics['memoryPeakBytes'] == 4294967296 and metrics['swapCurrentBytes'] == 0
    assert metrics['memoryEvents']['max'] == '15296'
    assert metrics['memoryEvents']['oom'] == metrics['memoryEvents']['oom_kill'] == '0'
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    assert not report['countryGraphChanged'] and not report['appActivated']
    return {**result, 'nationalRelationMetadataRunCompleted': True, 'completeRelationCount': 1624265,
            'supportedSourceTurnsMatched': 409178, 'unsupportedRelationsRetained': 70376,
            'closureWayIdsMatched': 149699, 'newUniqueClosedAllocationBytes': 2384539648,
            'uniqueClosedRoots': 90, 'nationalGraphCorrectionBuilt': False,
            'reads': 'Small bound records/code only; no PBF/ignored relation metadata/graph/model/provider/DB operation.'}


if __name__ == '__main__':
    print(json.dumps(verify()))
