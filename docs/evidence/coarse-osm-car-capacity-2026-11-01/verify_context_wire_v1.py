"""Portable proof of complete source-audited context records and wire bytes."""
import json

from verify_context_records_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    pack = stage('context-wire', False)
    audit = stage('context-wire-audit', False)
    assert pack['coreCompressedBytes'] == 46206142
    assert pack['contextRawBytes'] == 1746705 and pack['contextCompressedBytes'] == 441805
    assert audit['status'] == 'independent_complete_context_wire_bytes_passed'
    assert audit['copiedCoreFieldsByteIdentical'] == 12
    assert audit['replacementCoreBytesIndependentlyDecoded'] == 1404078
    assert audit['contextFieldsIndependentlyDecoded'] == 6 and audit['contextBytesIndependentlyCompared'] == 1746705
    assert audit['combinedCoreAndContextCompressedBytes'] == 46647947
    assert audit['sourcePbfReads'] == audit['nativeProducerExecutions'] == audit['routingQueries'] == 0
    total = result['newUniqueClosedAllocationBytes']
    for name in ('context-wire', 'context-wire-audit'):
        total += load(HERE/f'{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6884077568
    return {**result, 'contextWireAllChangedBytesIndependentlyDecoded': True,
            'contextWireCoreAndAuxCompressedBytes': 46647947,
            'uniqueClosedRoots': 235, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
