"""Check the saved comparison and its allocation ledger without running either model."""
import json
import math

from verify_entry_runtime_v1 import stage
from verify_finer_reused_display_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    plan = load(HERE / 'display-refinement-preview-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO / name) == pin, name
    report = stage('display-refinement-preview-v1')
    closed = load(HERE / 'display-refinement-preview-v1-closed-v1.json')
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 412
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < plan['maxOwnedBytes']
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    assert report['recipeSha256'] == sha(HERE / 'display-refinement-preview-plan-v1.json')
    assert report['status'] == 'all37_saved_production_display_comparisons_prepared'
    assert report['providerRequests'] == report['modelQueries'] == 0
    before, after = (load(REPO / plan[name]) for name in ['beforeReport', 'afterReport'])
    expected = []
    for old, new in zip(before['phases'], after['phases']):
        assert old['origin'] == new['origin']
        for a, b in zip(old['productions'], new['productions']):
            assert a['minutes'] == b['minutes']
            expected.append({'origin': old['origin'], 'minutes': a['minutes'],
                             'oldStep': a['frame']['step'] / 1e6, 'step': b['frame']['step'] / 1e6})
    assert report['cases'] == expected and len(expected) == 37
    metrics = report['metrics']
    assert metrics['commonCases'] == metrics['oldReached'] == metrics['newReached'] == 83
    for label, source in [('old', before), ('new', after)]:
        for suffix, metric in [('Mae', 'meanAbsoluteMinutes'), ('P90', 'p90AbsoluteMinutes')]:
            assert math.isclose(metrics[label + suffix], source['overall']['candidate'][metric],
                                rel_tol=0, abs_tol=1e-10)
        assert metrics[label + 'FailedGates'] == [k for k, v in source['gates'].items() if not v]
    html = closed['roster']['index.html']
    assert html['ignoredLargeAsset'] and html['bytes'] == report['htmlBytes'] < 67108864
    assert html['sha256'] == report['htmlSha256']
    assert report['hostTotalMsIncludingBindingsMapReadsVerificationHTMLAndIO'] < plan['hostSeconds'] * 1000
    return {**result, 'status': 'all37_saved_comparison_pairs_and_all83_metrics_reconciled',
            'registeredClosedRoots': 413, 'newUniqueClosedAllocationBytes': total,
            'comparisonModelQueries': 0, 'comparisonProviderRequests': 0,
            'comparisonPairs': 37, 'comparisonHtmlSha256': html['sha256'],
            'largeHtmlReadByThisProof': False, 'fullAppCameraAdmission': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
