"""Reconcile the bounded offline index probe with already audited source counts."""
import json

from verify_preparation_v1 import HERE, closed, load
from verify_source_quality_v2 import verify as source_quality


def verify():
    source_quality()
    root, _ = closed('node-index', 'build', 'v1', 0)
    binary = load(root/'result.json')
    assert binary['artifactSha256'] == '738dacb8442e32ed296ecb9d04fcd19fe6b954fc9832d25554073ad7facedd97'
    assert binary['artifactBytes'] == 426672
    failed, _ = closed('node-index', 'controls', 'v1', 2)
    assert load(failed/'worker-failure.json')['errorType'] == 'ModuleNotFoundError'
    root, _ = closed('node-index', 'controls', 'v2', 0)
    assert load(root/'controls.json') == {'tests': 9, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    root, plan = closed('node-index', 'probe', 'v2', 0)
    result = load(root/'result.json')
    assert (result['references'], result['selectedNodes'], result['anchors'], result['referenceLookups']) == (48163649, 42993567, 5731903, 48163649)
    assert result['indexAllocatedBytes'] == 1907546388 and result['typedSourceMergePasses'] == 2 and result['complete'] == 1
    assert result['sourcePbfReads'] == result['coordinateRowsLoaded'] == result['networkRequests'] == result['applicationDbReads'] == 0
    assert not any(result[key] for key in ('countryCostsBuilt', 'retainedIndexOnDisk', 'modelChanged'))
    inputs = {name: pin for name, pin in plan['inputs'].items() if '/streams/' in name}
    audit = load(HERE/'node-index-probe-audit-plan-v1.json')
    original = load(HERE/'capacity-raw/derive-v2/execution-plan.json')['inputs']
    assert len(inputs) == 32 and inputs == audit['sourceFiles']
    assert all(original[name] == pin for name, pin in inputs.items())
    return {'targetLinuxControls': 9, 'nativeReferenceLookupsChecked': 48163649,
            'selectedNodeOrdinalsChecked': 42993567, 'anchorOrdinalsChecked': 5731903,
            'offlineIndexAllocatedBytes': 1907546388,
            'scope': 'Independent synthetic list/cut oracles plus actual native self-check and closed-record reconciliation. No new independent per-node country oracle, coordinates, routing costs or Vercel admission.',
            'reads': 'Small mirrored records and repository code only.'}


if __name__ == '__main__':
    print(json.dumps(verify()))
