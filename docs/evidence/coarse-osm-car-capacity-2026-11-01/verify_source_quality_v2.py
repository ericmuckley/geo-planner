"""Verify preserved invalid-source evidence and the separately versioned policy."""
import json

from verify_country_v3 import verify as country
from verify_preparation_v1 import HERE, closed, load, sha


def verify():
    country()
    failed, _ = closed('capacity', 'relation-inspect', 'v3', 2)
    assert load(failed/'worker-failure.json')['errorType'] == 'RuntimeError'
    root, _ = closed('capacity', 'relation-inspect', 'v4', 0)
    diagnosis = load(root/'audit.json')
    assert diagnosis['selfTests']['successful'] and diagnosis['selfTests']['checks'] == 3
    assert diagnosis['pythonObjectsProjectedFromCountry'] == 2
    assert diagnosis['parentReceiptSha256'] == sha(HERE/'capacity-raw/run-v3/receipt.json')
    assert len(diagnosis['records']) == 2
    for record in diagnosis['records']:
        assert record['tags']['type'] == 'restriction'
        assert record['members'] and all(m['type'] == 'relation' for m in record['members'])
        assert not any(m['type'] in ('node', 'way') for m in record['members'])
    root, _ = closed('car', 'build', 'v2', 0)
    binary = load(root/'result.json')
    assert binary['artifactSha256'] == '2ad560409e0d360ba981e2808e2932e21ebf9bcf8784e4717210bd9a4bb7cc26'
    assert binary['artifactBytes'] == 1729936
    root, _ = closed('car', 'controls', 'v2', 0)
    assert load(root/'controls.json') == {'tests': 19, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    root, _ = closed('car', 'equivalence', 'v2', 0)
    result = load(root/'result.json')
    assert (result['selectedNodes'], result['majorWays'], result['relations'], result['sourceWaysExamined']) == (143560, 28995, 4900, 239253)
    assert result['invalidSourceRecordsRetainedAndCompared'] == 2
    assert result['existingCapturedDecisionsUnchanged'] and not result['policyV2QualifiedOnCountry']
    return {'selectedSourceRecordsInspected': 2, 'genericInvalidSourcePolicyLinuxTests': 19,
            'existingCapturedMetadataDecisionsUnchanged': 177455,
            'v1CountryRecordUnchanged': True, 'countryTimingGraphBuilt': False,
            'reads': 'Small mirrored evidence and repository code only; no ignored assets or worker/provider/DB execution.'}


if __name__ == '__main__':
    print(json.dumps(verify()))
