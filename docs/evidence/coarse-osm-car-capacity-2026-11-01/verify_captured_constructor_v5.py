"""Portable complete captured constructor/source/native-point/query proof."""
import json

from verify_constructor_v1 import verify as preparation
from verify_preparation_v1 import closed, load


def verify():
    preparation()
    root, _ = closed('graph-capture', 'run', 'v3', 2)
    assert load(root/'preparation-controls.json')['tests'] == 11
    assert load(root/'worker-failure.json')['error'] == 'Captured constructor source typed ID order'
    root, _ = closed('graph-capture', 'run', 'v4', 2)
    assert load(root/'preparation-controls.json') == {'tests': 14, 'successful': False, 'failures': 0, 'errors': 1, 'skips': 0}
    assert 'Returned non-highway way' in (root/'worker.log').read_text()
    root, _ = closed('graph-capture', 'run', 'v5', 0)
    result = load(root/'audit.json');facts = result['facts'];conversion = result['conversion']
    assert load(root/'preparation-controls.json') == {'tests': 14, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    assert conversion['rows'] == result['capturedJsonlRecordsValidated'] == 1368072
    assert conversion['bytes'] == 477852579 and conversion['sha256'] == 'efc36dc058b198711cc2666a751c9fd60b52d37902efbb22e1cba8b5f30f91f4'
    assert conversion['inputOrder'] == 'node/relation/way' and conversion['generatedOrder'] == 'node/way/relation'
    assert result['receipt']['nativeEof'] and result['receipt']['pythonProjectionFrames'] == 0
    assert result['receipt']['semanticSha256'] == conversion['semanticSha256']
    assert (facts['selectedNodes'], facts['anchors'], facts['majorWays'], facts['majorReferences'], facts['nonzeroLineageSegments']) == (143560, 46881, 28995, 177956, 52282)
    assert (facts['preClosureArcs'], facts['postClosureArcs'], facts['outputBytes']) == (78811, 75137, 6869789)
    assert facts['selectedCoordinatesSeen'] == 143560 and facts['preClosureCostOverflows'] == facts['postClosureCostOverflows'] == 0
    root, _ = closed('graph-capture', 'audit', 'v5', 0)
    audit = load(root/'audit.json');queries = audit['queries']
    assert (audit['selectedNativeCoordinatesChecked'], audit['anchorsAndFlagsChecked'], audit['sourceGeometryReferencesChecked']) == (143560, 46881, 177956)
    assert (audit['preClosureArcCostsChecked'], audit['postClosureArcCostsChecked']) == (78811, 75137)
    assert audit['sourceWaysExamined'] == 239253 and audit['majorWayGeometryMetadataChecked'] == 28995 and audit['relationsExamined'] == 4900
    assert audit['supportedSourceTurnsChecked'] == 4078
    assert queries['originalDirectionalCases'] == len(queries['checks']) == 82 and queries['unreachableCasesPreserved'] == 14
    assert queries['exactRawCostsAllMatch'] and queries['quantizedCostsNeverWorse'] and queries['quantizedCasesImproved'] == 0
    assert queries['allNativePointsRetained'] == 143560 and queries['internalPaidAliases'] == 96679
    assert audit['sourcePbfReads'] == audit['nativeLibraryExecutions'] == audit['networkRequests'] == audit['applicationDbReads'] == 0
    return {'targetConstructorLinuxControls': 83, 'targetPreparationControls': 14,
            'everyCapturedNativePointVerified': 143560, 'everyPreClosureArcCostVerified': 78811,
            'allOriginalDirectionalCostsExactlyMatched': 82, 'unreachableCasesPreserved': 14,
            'quantizedCostsExactlyPreservedForAllOriginalCases': True,
            'countryCostsOrAppQualified': False, 'reads': 'Small mirrored evidence and repository code only.'}


if __name__ == '__main__':
    print(json.dumps(verify()))
