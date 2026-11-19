"""Portable timing runtime lineage proof; small mirrors only, no producer replay."""
import json

from verify_tagged_timing_graph_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    prefixes = [
        'tagged-timing-derived-controls', 'tagged-timing-derived-spatial',
        'tagged-timing-derived-geometry', 'tagged-timing-context-controls',
        'tagged-timing-context-run', 'tagged-timing-codec-core',
        'tagged-timing-codec-geometry', 'tagged-timing-codec-audit-core',
        'tagged-timing-codec-audit-geometry', 'tagged-timing-context-wire',
        'tagged-timing-context-wire-audit', 'tagged-timing-access',
    ]
    reports = {name: stage(name, index < 5) for index, name in enumerate(prefixes)}
    for name, tests in [('derived', 37), ('context', 22)]:
        assert reports['tagged-timing-'+name+'-controls']['controls'] == dict(
            tests=tests, successful=True, failures=0, errors=0, skips=0)
    spatial = reports['tagged-timing-derived-spatial']['independentAudit']
    assert spatial['directedArcsCostsPhysicalReversesChecked'] == 9826630
    assert spatial['forbiddenTurnPairsChecked'] == 258059
    assert spatial['spatialCellsChecked'] == 56970
    geometry = reports['tagged-timing-derived-geometry']['independentAudit']
    assert geometry['physicalSpansChecked'] == 6586963
    assert geometry['directedSourceCostsChecked'] == 9826630
    assert geometry['interiorPositionsChecked'] == 695833
    assert geometry['longSpansChecked'] == 533417
    assert geometry['runtimeBytes'] == 11561434
    assert geometry['maximumDiscardedSourcePointErrorMeters'] <= 100
    assert geometry['maximumDiscardedSourceTimeErrorMs'] <= 10000
    history = reports['tagged-timing-context-run']
    assert history['status'] == 'multiway_static_bans_and_single_via_context_records_source_audited'
    assert history['contextStates'] == 34179
    assert history['prohibitedExitArcRecords'] == 22643
    assert history['activeTriggerPairs'] == 22628
    assert history['retainedStaticForbiddenPairs'] == 237741
    assert history['finalForbiddenUnionPairsChecked'] == 258059
    assert history['contextRuntimeBackingBytes'] == 1786511
    assert history['additionalQueryLabelBytes'] == 136716
    assert history['requiresTurnContextSearch']
    for kind, fields, raw, compressed in [
        ('core', 13, 129632810, 46353814),
        ('geometry', 7, 11561434, 7957188),
    ]:
        encoded = reports['tagged-timing-codec-'+kind]
        audited = reports['tagged-timing-codec-audit-'+kind]
        assert encoded['fields'] == audited['fields'] == fields
        assert encoded['rawBytes'] == audited['bytesIndependentlyDecodedAndCompared'] == raw
        assert encoded['compressedBytes'] == audited['compressedBytes'] == compressed
    wire = reports['tagged-timing-context-wire']
    audited = reports['tagged-timing-context-wire-audit']
    assert wire['copiedCoreFieldsByteIdentical'] == audited['copiedCoreFieldsByteIdentical'] == 12
    assert wire['contextRawBytes'] == audited['contextBytesIndependentlyCompared'] == 1786511
    assert wire['combinedCoreAndContextCompressedBytes'] == audited['combinedCoreAndContextCompressedBytes'] == 46811006
    access = reports['tagged-timing-access']
    assert access['inputs'] == access['supported'] == access['newEndpointCollections'] == 79
    assert access['originalSupportedInputsRetained'] == 78
    assert access['totalConnections'] == 10338 and access['maximumConnections'] == 1840
    assert access['reusedEndpointCollections'] == access['unsupported'] == access['maskOmissionAllowanceInputs'] == 0
    total = result['newUniqueClosedAllocationBytes'] + sum(
        load(HERE/(name+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
        for name in prefixes)
    assert total == 9332916224
    assert 64500000000 + total + 104857600 + 268435456 < 72 * 1024**3
    return {**result, 'status': 'complete_estimated_timing_runtime_source_and_storage_audits_passed',
            'freshCostDependentGeometryHistoriesAndAll79EndpointCollections': True,
            'all141194244CoreAndGeometrySourceBytesIndependentlyCompared': True,
            'uniqueClosedRoots': 318, 'newUniqueClosedAllocationBytes': total,
            'fullGridCandidateAccuracyMeasuredByThisProof': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
