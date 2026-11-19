"""Verify the new runtime and endpoints from portable receipts."""
import json

from verify_conditional_only_graph_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result = previous()
    total = result['newUniqueClosedAllocationBytes']
    roots = result['registeredClosedRoots']
    reports = {}
    closures = {}
    for name, native in [('derived-spatial', True), ('derived-geometry', True),
                         ('context-run', True), ('runtime', False), ('access', False)]:
        prefix = 'conditional-only-' + name
        raw = HERE / (prefix + '-raw-v1')
        plan = load(raw / 'execution-plan.json')
        assert sha(raw / 'execution-plan.json') == sha(HERE / (prefix + '-plan-v1.json'))
        assert plan['previousClosedRoots'] == roots and plan['newClosedAllocationBytes'] == total
        reports[name] = stage(prefix, native)
        closures[name] = load(HERE / (prefix + '-closed-v1.json'))
        total += closures[name]['usage']['conservativeAllocatedBytes']
        roots += 1
    spatial = reports['derived-spatial']['independentAudit']
    assert spatial['directedArcsCostsPhysicalReversesChecked'] == 9853924
    assert spatial['verticesChecked'] == 5731903 and spatial['forbiddenTurnPairsChecked'] == 260017
    geometry = reports['derived-geometry']['independentAudit']
    assert geometry['directedSourceCostsChecked'] == 9853924 and geometry['physicalSpansChecked'] == 6601900
    assert geometry['maximumDiscardedSourcePointErrorMeters'] <= 100
    assert geometry['maximumDiscardedSourceTimeErrorMs'] <= 10000
    context = reports['context-run']
    assert context['completePreArcsMapped'] == 9882872 and context['retainedArcsMapped'] == 9853924
    assert context['multiPreEntryPairs'] == 2652 and context['finalForbiddenUnionPairsChecked'] == 260017
    assert context['oldAllowedPathsRemainOrdinary'] and context['requiresTurnContextSearch']
    assert context['contextStates'] == 34256 and context['contextRuntimeBackingBytes'] == 1790787
    plan = load(HERE / 'conditional-only-context-run-plan-v1.json')
    assert plan['staticEntryInputs'] == {
        'priorMultiVia': 2614, 'newMandatory': 38, 'staticUnion': 2652,
        'combinedWithSingleEntry': 25436,
        'staticUnionSha256': sha(HERE / 'conditional-only-static-entry-pairs-v1.u32'),
    }
    runtime = reports['runtime']
    assert runtime['status'] == 'mandatory_runtime_packed_and_verified_by_existing_loaders'
    assert runtime['graphArcs'] == 9853924 and runtime['contextStates'] == 34256
    for kind, count in [('core', 13), ('geometry', 7), ('context', 6)]:
        manifest = load(HERE / 'conditional-only-runtime-raw-v1' / kind / 'manifest.json')
        roster = closures['runtime']['roster']
        assert runtime[kind]['manifestSha256'] == roster[kind + '/manifest.json']['sha256']
        assert runtime[kind]['fields'] == len(manifest['fields']) == count
        for name, field in manifest['fields'].items():
            if kind == 'geometry':
                raw = closures['derived-geometry']['roster'][name]
            elif kind == 'context' or name == 'routing/forbidden-turns.u24':
                raw = closures['context-run']['roster']['records/' + name]
            else:
                raw = closures['derived-spatial']['roster'][name]
            assert (field['rawBytes'], field['rawSha256']) == (raw['bytes'], raw['sha256'])
            packed = roster[kind + '/' + field['file']]
            assert (field['compressedBytes'], field['compressedSha256']) == (packed['bytes'], packed['sha256'])
    access = reports['access']
    assert access['inputs'] == access['newEndpointCollections'] == access['supported'] == 79
    assert access['reusedEndpointCollections'] == access['maskOmissionAllowanceInputs'] == 0
    assert access['originalSupportedInputsRetained'] == 78 and access['totalConnections'] == 10422
    for row in access['rows']:
        item = row['output']
        expected = closures['access']['roster'][item['filename']]
        assert (item['compressedBytes'], item['sha256']) == (expected['bytes'], expected['sha256'])
    assert roots == 434 and total == 11403288576
    assert 64500000000 + total + 104857600 + 268435456 < 72 * 1024 ** 3
    return {
        'status': 'mandatory_runtime_and_all_benchmark_endpoints_qualified',
        'registeredClosedRoots': roots,
        'newUniqueClosedAllocationBytes': total,
        'graphArcs': 9853924,
        'compressedRuntimeDataBytes': runtime['combinedCompressedBytes'],
        'freshBenchmarkEndpointCollections': 79,
        'accuracyOrAppAccepted': False,
    }


if __name__ == '__main__':
    print(json.dumps(verify()))
