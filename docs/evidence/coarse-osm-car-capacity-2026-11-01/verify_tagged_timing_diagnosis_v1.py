"""Metadata-only current timing diagnosis; no ignored assets or producer replay.

Historical full-workspace proofs remain separate: some read three legacy cached
inputs. This checks the current receipts/code and the frozen allocation ledger.
"""
import json
import math

from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    native = [
        'country-controls', 'country-run', 'graph-controls', 'graph-run',
        'derived-controls', 'derived-spatial', 'derived-geometry',
        'context-controls', 'context-run', 'attributes-controls', 'attributes-run',
    ]
    host = [
        'routing-capture', 'codec-core', 'codec-geometry', 'codec-audit-core',
        'codec-audit-geometry', 'context-wire', 'context-wire-audit', 'access',
        'evaluation', 'shading', 'paths',
    ]
    reports = {name: stage('tagged-timing-'+name, name in native) for name in native + host}
    for name, tests in [('graph', 38), ('derived', 37), ('context', 22), ('attributes', 9)]:
        assert reports[name+'-controls']['controls'] == dict(
            tests=tests, successful=True, failures=0, errors=0, skips=0)
    country = reports['country-run']
    assert country['everyOldAndNewMacroPricePythonAudited'] == 9882872
    assert country['allPhysicalArcDescriptorsAndOrderExact']
    assert country['allDirectionsDefaultsRolesAndFlagsExact']
    assert not country['originalLegalSpeedSourceFactsModified']
    history = reports['context-run']
    assert history['contextStates'] == 34179 and history['retainedStaticForbiddenPairs'] == 237741
    assert history['finalForbiddenUnionPairsChecked'] == 258059
    for kind, raw, compressed in [('core', 129632810, 46353814), ('geometry', 11561434, 7957188)]:
        assert reports['codec-'+kind]['rawBytes'] == reports['codec-audit-'+kind]['bytesIndependentlyDecodedAndCompared'] == raw
        assert reports['codec-'+kind]['compressedBytes'] == reports['codec-audit-'+kind]['compressedBytes'] == compressed
    assert reports['context-wire-audit']['copiedCoreFieldsByteIdentical'] == 12
    assert reports['context-wire-audit']['contextBytesIndependentlyCompared'] == 1786511
    assert reports['access']['supported'] == reports['access']['newEndpointCollections'] == 79
    candidate = reports['evaluation']
    assert len(candidate['rows']) == candidate['originalCases'] == 83
    assert candidate['overall']['candidate']['pairedFinite'] == 83
    assert candidate['overall']['candidate']['meanAbsoluteMinutes'] == 13.910366465863454
    assert not candidate['numericalGatesPassed'] and not candidate['candidateAdmitted']
    failed = sorted(key for key, value in candidate['gates'].items() if not value)
    assert failed == sorted(['originalMean', 'originalP90', 'horizonP90', 'valhallaOriginalMean',
                             'valhallaRegionalMean', 'frontierWorstRegression', 'olderWorstRegression', 'all35OlderShaded'])
    assert candidate['diagnosticDisplays'] == 21 and candidate['productionDisplays'] == 37
    assert not candidate['frozenLocalGridOrMapsReused'] and candidate['providerRequests'] == 0
    assert candidate['retainedBackingBytes'] == 159687884
    paths = reports['paths']
    assert paths['paths'] == len(paths['rows']) == 83 and paths['unavailable'] == 0
    assert paths['reusedRoadPaths'] == paths['providerRequests'] == 0 and len(paths['phases']) == 21
    assert paths['afterLoad']['arrayBuffers'] == paths['afterQueries']['arrayBuffers'] == 159771358
    timings = {row['id']: row['candidate']['pointMinutes'] for row in candidate['rows']}
    for row in paths['rows']:
        assert sum(row['components'].values()) == row['sumTicks']
        assert math.isclose(row['sumTicks']/480, timings[row['id']], abs_tol=1e-9)
        if row['searchStats']:
            assert row['searchStats']['offlineSearchBackingBytes'] <= 96 * 1024**2
    attributes = reports['attributes-run']
    assert (attributes['paths'], attributes['unavailable'], attributes['selectedArcs']) == (83, 0, 41940)
    assert (attributes['waysChecked'], attributes['preArcMappingsChecked'], attributes['retainedArcMappingsChecked']) == (4227238, 9882872, 9826630)
    assert attributes['sourcePbfReads'] == attributes['routingQueries'] == attributes['providerRequests'] == 0
    shading = reports['shading']
    assert len(shading['rows']) == 83 and len(shading['maps']) == 37
    assert shading['pointDryButCellCenterWet'] == ['Big Bear Lake', 'salton-city--bombay-beach']
    plan = load(HERE/'tagged-timing-path-findings-plan-v1.json')
    artifact_path = 'data/coarse-quality/us-osm-tagged-timing-attributes-run-v1/arc-attributes.json.gz'
    for name, pin in plan['bindings'].items():
        if name.startswith('data/'):
            assert name == artifact_path
            closed = load(HERE/'tagged-timing-attributes-run-closed-v1.json')
            assert pin == closed['roster']['arc-attributes.json.gz']['sha256']
        else:
            assert sha(REPO/name) == pin, name
    findings = load(HERE/'tagged-timing-path-findings-v1.json')
    assert findings['recipeSha256'] == sha(HERE/'tagged-timing-path-findings-plan-v1.json')
    assert len(findings['rows']) == 83 and not findings['unavailable']
    assert findings['sourceSpeedAttributeUniqueKnownArcs'] == 41940
    assert findings['sourceSpeedAttributeUniqueUnknownArcs'] == 0
    assert findings['providerRequests'] == findings['modelQueries'] == 0 and not findings['policyChanged']
    prefixes = ('lane-restrictions-', 'lane-graph-', 'lane-derived-', 'lane-codec-',
                'lane-context-', 'lane-access-', 'lane-points-', 'lane-road-', 'tagged-timing-')
    ledger = [load(p) for p in HERE.glob('*-closed-v1.json') if p.name.startswith(prefixes)]
    assert len({row['root'] for row in ledger}) == len(ledger) == 46
    total = 7884292096 + sum(row['usage']['conservativeAllocatedBytes'] for row in ledger)
    assert total == plan['newClosedAllocationBytes'] == 9365839872
    assert plan['previousClosedRoots'] == 277 + len(ledger) == 323
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    return {'status': 'current_timing_candidate_all83_winners_source_and_cached_geometry_audited',
            'currentClosedReceiptsChecked': len(reports), 'registeredClosedRoots': 323,
            'newUniqueClosedAllocationBytes': total, 'all83FiniteWinnerSumsReproduced': True,
            'selectedSourceArcsKnown': 41940, 'selectedSourceArcsUnknown': 0,
            'meanAbsoluteMinutes': 13.910366465863454, 'failedOriginalGates': failed,
            'ignoredAssetsReadOrProducerExecutions': 0, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
