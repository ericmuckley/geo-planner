"""Portable compiled/native/captured equivalence proof; no binary execution."""
import json
from verify_entry_records_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, closed, load, sha


def verify():
    result = previous()
    root, _ = closed('entry-native', 'build', 'v1', 0)
    artifact = load(root/'result.json')
    assert artifact['artifactSha256'] == '81aaf6c74b73c7c7dbf9355d94a5e1feb817c980808a90c5d23d1e1a42ea717f'
    assert artifact['artifactBytes'] == 2068704
    root, _ = closed('entry-native', 'controls', 'v1', 0)
    assert load(root/'controls.json') == {'tests': 12, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    root, _ = closed('entry-native', 'equivalence', 'v1', 0)
    matched = load(root/'result.json')
    assert matched['resolvedCounts'] == [461, 295, 165, 1, 1711, 1038, 292, 78811, 76426]
    assert matched['augmentationCounts'] == [292, 2423, 271, 21, 2650, 76426]
    assert matched['filesByteIdentical'] == 11 and matched['bytesIndependentlyCompared'] == 1037031
    assert matched['queriesExecutedHere'] == matched['sourcePbfReads'] == matched['sourceConstructorExecutions'] == matched['providerRequests'] == 0
    record = load(HERE/'entry-resolution-controls-closed-v1.json')
    root = HERE/'entry-resolution-controls-raw-v1'
    for name, pin in record['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (root/name).stat().st_size == pin['bytes'] and sha(root/name) == pin['sha256']
    for name, pin in load(root/'execution-plan.json')['inputs'].items():
        assert sha(REPO/name) == pin
    assert load(root/'report.json')['controls'] == {'tests': 8, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    assert load(root/'cleanup.json')['independentInspectAbsent']
    return {**result, 'nativeEntryLinuxControls': 12, 'capturedCorrectedFieldsByteIdentical': 11,
            'independentResolutionAuditControls': 8, 'newUniqueClosedAllocationBytes': 2404130816,
            'uniqueClosedRoots': 95, 'nationalEntryArcsResolved': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
