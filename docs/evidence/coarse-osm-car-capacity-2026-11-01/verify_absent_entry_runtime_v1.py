"""Portable complete absent-member spatial/geometry/storage proof; no replay."""
import json

from verify_absent_entry_country_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    assert stage('absent-entry-derived-controls', True)['controls'] == dict(tests=37, successful=True, failures=0, errors=0, skips=0)
    spatial = stage('absent-entry-derived-spatial', True)
    assert spatial['nativeResult']['arcs'] == spatial['independentAudit']['directedArcsCostsPhysicalReversesChecked'] == 9807359
    assert spatial['independentAudit']['forbiddenTurnPairsChecked'] == 252230
    assert spatial['independentAudit']['spatialCellsChecked'] == 56970
    geometry = stage('absent-entry-derived-geometry', True)
    proof = geometry['independentAudit']
    assert proof['physicalSpansChecked'] == 6568401 and proof['directedSourceCostsChecked'] == 9807359
    assert proof['curvedSpansChecked'] == 299216 and proof['interiorPositionsChecked'] == 695664
    assert proof['longSpansChecked'] == 533359 and proof['lengthOverflowsChecked'] == 0
    assert proof['runtimeBytes'] == geometry['nativeResult']['runtimeBytes'] == 11559293
    assert proof['maximumDiscardedSourcePointErrorMeters'] <= 100 and proof['maximumDiscardedSourceTimeErrorMs'] <= 10000
    stages = ['derived-controls', 'derived-spatial', 'derived-geometry']
    for kind, fields, raw, compressed in [('core', 13, 129482210, 46234772), ('geometry', 7, 11559293, 7955432)]:
        encoded = stage('absent-entry-codec-'+kind)
        audited = stage('absent-entry-codec-audit-'+kind)
        assert encoded['fields'] == audited['fields'] == fields
        assert encoded['rawBytes'] == audited['bytesIndependentlyDecodedAndCompared'] == raw
        assert encoded['compressedBytes'] == audited['compressedBytes'] == compressed
        assert audited['nativeProducerExecutions'] == audited['routingQueries'] == audited['sourcePbfReads'] == 0
        stages.extend(['codec-'+kind, 'codec-audit-'+kind])
    total = result['newUniqueClosedAllocationBytes']
    for name in stages:
        total += load(HERE/f'absent-entry-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6783492096
    return {**result, 'absentMemberRuntimeStorageEveryByteChecked': 141041503,
            'absentMemberCoreAndGeometryCompressedBytes': 54190204,
            'uniqueClosedRoots': 220, 'newUniqueClosedAllocationBytes': total,
            'absentMemberActualLoaderOrAccuracyMeasured': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
