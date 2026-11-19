"""Portable conditional-source complete geometry/storage-byte proof."""
import json
from verify_conditional_geometry_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    total = result['newUniqueClosedAllocationBytes']
    for kind, fields, raw, compressed in [('core', 13, 129092816, 46135184), ('geometry', 7, 11534916, 7942463)]:
        encoded = stage('conditional-codec-'+kind)
        audited = stage('conditional-codec-audit-'+kind)
        assert encoded['fields'] == audited['fields'] == fields
        assert encoded['rawBytes'] == audited['bytesIndependentlyDecodedAndCompared'] == raw
        assert encoded['compressedBytes'] == audited['compressedBytes'] == compressed
        assert audited['nativeProducerExecutions'] == audited['routingQueries'] == audited['sourcePbfReads'] == 0
        for prefix in ('conditional-codec-'+kind, 'conditional-codec-audit-'+kind):
            total += load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == 6316077056
    return {**result, 'conditionalRuntimeStorageEveryByteChecked': 140627732,
            'conditionalCoreAndGeometryCompressedBytes': 54077647,
            'uniqueClosedRoots': 196, 'newUniqueClosedAllocationBytes': total,
            'conditionalActualLoaderOrAccuracyMeasured': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
