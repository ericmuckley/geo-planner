"""Check closed country-count evidence without reading ignored source/graph assets."""
import json

from verify_preparation_v1 import HERE, closed, load, sha, verify as preparation


def verify():
    preparation()
    root, plan = closed('capacity', 'run', 'v3', 0)
    result = load(root/'result.json')
    receipt = load(root/'receipt.json')
    assert receipt['nativeEof'] and receipt['projectedFrames'] == receipt['fallbacks'] == 0
    assert receipt['visits'] == 1770542426
    assert receipt['semanticSha256'] == '209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    identity = receipt['sourceIdentity']
    assert identity['sourceSha256'] == '1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
    assert identity['framingBytesRead'] == 12229320016 and identity['frames'] == 221321
    assert identity['publisherStateUtc'] == '2026-10-25T21:21:21Z'
    assert (result['majorWays'], result['majorReferences'], result['nonzeroLineageSegments']) == (4227238, 48163649, 6674747)
    assert (result['preClosureArcs'], result['postLocatableClosureArcs']) == (9837326, 9620680)
    assert result['wayFactRows'] == 4227238 and result['wayFactBytes'] == 135271616
    assert result['unlocatableRestrictions'] == 2 and not result['policyFullyLocatable']
    assert not any(result[key] for key in ('nationalGraphBuilt', 'etaQualified', 'vercelQualified', 'modelChanged', 'networkRequests', 'applicationDbReads'))
    footprint = load(HERE.parents[0]/'coarse-osm-national-footprint-2026-11-01/raw-run-v1/receipt.json')
    for key in ('metadata', 'histogram', 'semanticSha256', 'sourceIdentity'):
        assert receipt[key] == footprint[key], key
    audit_root, _ = closed('capacity', 'country-audit', 'v3', 0)
    audit = load(audit_root/'audit.json')
    assert audit['resultSha256'] == sha(root/'result.json')
    assert audit['artifactsSha256'] == sha(root/'artifacts.json')
    assert audit['auditorSha256'] == sha(HERE/'country_audit_v2.py')
    assert audit['wayRowsChecked'] == 4227238 and audit['factFiles'] == 9
    assert audit['preClosureArcsChecked'] == result['preClosureArcs']
    assert audit['postLocatableClosureArcsChecked'] == result['postLocatableClosureArcs']
    assert audit['sourcePbfReads'] == audit['nativeLibraryExecutions'] == 0
    vertices = 5731903
    packed_base = 12*vertices + 6*result['preClosureArcs'] + 3
    assert packed_base == 127806795
    assert 162238546-packed_base == 34431751
    return {'countryCountComplete': True, 'independentlyCheckedWayFacts': 4227238,
            'preClosureArcs': 9837326, 'postLocatableClosureArcs': 9620680,
            'packedBaseArithmeticBytes': packed_base, 'policyFullyLocatable': False,
            'appOrEtaAdmission': False, 'reads': 'Small closed mirrors and repository code only.'}


if __name__ == '__main__':
    print(json.dumps(verify()))
