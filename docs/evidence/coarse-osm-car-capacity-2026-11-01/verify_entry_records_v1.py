"""Portable typed metadata proof; never transform ignored source metadata again."""
import json
from verify_preparation_v1 import HERE, REPO, load, sha
from verify_relation_metadata_v1 import verify as previous
from verify_spatial_storage_v1 import host_closed


def verify():
    result = previous()
    root = host_closed('entry-records')
    report, controls = load(root/'report.json'), load(HERE/'entry-record-controls-v1.json')
    assert controls['tests'] == 7 and controls['successful'] and controls['failures'] == controls['skips'] == 0
    for name, pin in controls['codeBindings'].items():
        assert sha(REPO/name) == pin
    assert report['status'] == 'typed_national_entry_metadata_prepared'
    assert (report['sourceRows'], report['sourceBytes']) == (70376, 21119251)
    assert (report['candidateRules'], report['fallbackRelations'], report['fallbackClosureIds']) == (46533, 23843, 39869)
    assert report['candidateBytes'] == 46533*32 and report['fallbackBytes'] == 39869*8
    assert report['originalClosureIdsVerified'] == 149699 and not report['actualArcResolutionPerformed']
    assert not report['ruleShapePolicyChanged'] and not report['countryGraphChanged']
    assert report['sourcePbfReads'] == report['graphQueries'] == 0
    closed = load(HERE/'entry-records-closed-v1.json')
    for name, asset in report['assets'].items():
        assert closed['roster'][name]['sha256'] == asset['sha256'] and closed['roster'][name]['bytes'] == asset['bytes']
    return {**result, 'typedNationalEntryCandidates': 46533, 'noncandidateFallbackRelations': 23843,
            'newUniqueClosedAllocationBytes': 2387464192, 'uniqueClosedRoots': 91,
            'nationalEntryArcsResolved': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
