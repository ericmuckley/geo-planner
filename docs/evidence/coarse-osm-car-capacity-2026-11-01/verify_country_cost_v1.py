"""Portable national native geometry/cost and independent derived-audit proof."""
import json
from verify_preparation_v1 import closed, load


def verify():
    root, _ = closed('country-cost', 'controls', 'v1', 0)
    assert load(root/'preparation-controls.json') == {'tests': 21, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    root, _ = closed('country-cost', 'run', 'v1', 0)
    result = load(root/'audit.json');facts = result['facts']
    assert result['status'] == 'passed_guarded_national_native_geometry_cost_facts'
    assert result['guardedSourceScanInvocations'] == 1 and result['ordinaryPythonNationalSourceObjects'] == 0
    assert (facts['selectedCoordinatesSeen'], facts['anchors'], facts['majorWays'], facts['majorReferences'], facts['nonzeroLineageSegments']) == (42993567, 5731903, 4227238, 48163649, 6674747)
    assert (facts['preClosureArcs'], facts['postClosureArcs'], facts['preClosureCostOverflows'], facts['postClosureCostOverflows']) == (9837326, 9620680, 2, 2)
    assert facts['outputBytes'] == 1376842205 and facts['complete'] == 1
    assert not result['appCsrReverseTurnPairsBuilt'] and not result['etaQualified'] and not result['vercelQualified'] and not result['modelChanged']
    receipt = load(root/'receipt.json')
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0
    root, _ = closed('country-cost', 'audit', 'v1', 0)
    audit = load(root/'audit.json')
    assert audit['status'] == 'independent_complete_national_derived_cost_fact_audit_passed'
    assert audit['topology'] == {'references': 48163649, 'selectedNativeIds': 42993567, 'sourceDefinedAnchors': 5731903}
    assert (audit['waysChecked'], audit['sourceGeometryReferencesChecked'], audit['physicalSpansChecked']) == (4227238, 48163649, 6674747)
    assert (audit['preClosureArcCostsChecked'], audit['postClosureArcCostsChecked']) == (9837326, 9620680)
    assert audit['preClosureCostOverflows'] == audit['postClosureCostOverflows'] == 2
    assert audit['supportedSourceTurnRecordsChecked'] == 409178 and audit['invalidSourceRecordsExactlyMatched'] == 2
    assert audit['sourcePbfReads'] == audit['nativeLibraryExecutions'] == audit['networkRequests'] == audit['applicationDbReads'] == 0
    assert not audit['etaQualified'] and not audit['vercelQualified'] and not audit['modelChanged']
    return {'nationalDerivedCostsChecked': 9620680, 'allSourceReferencesChecked': 48163649,
            'completeIndependentDerivedAudit': True, 'appOrEtaQualified': False,
            'reads': 'Small mirrored evidence and bound repository code only; no source, graph, worker, provider or DB execution.'}


if __name__ == '__main__':
    print(json.dumps(verify()))
