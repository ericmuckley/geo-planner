"""Verify exact captured native geometry/cost equivalence from small closed records."""
import json

from verify_node_index_v1 import verify as node_index
from verify_preparation_v1 import closed, load


def verify():
    node_index()
    root, _ = closed('cost-math', 'build', 'v1', 0)
    binary = load(root/'result.json')
    assert binary['artifactSha256'] == '0ac9ee0a4ceb909b124b2141c418bb90058e14874b1bfe85e9fc94a530957016'
    assert binary['artifactBytes'] == 422704
    root, _ = closed('cost-math', 'controls', 'v1', 0)
    assert load(root/'controls.json') == {'tests': 10, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    root, _ = closed('cost-math', 'equivalence', 'v1', 0)
    result = load(root/'result.json')
    assert (result['sourceWaysExamined'], result['majorWays'], result['sourcePrimitiveEdges']) == (239253, 28995, 148961)
    assert (result['directedPrimitiveCostsChecked'], result['contractedArcSumsAndTicksChecked']) == (218666, 86517)
    assert not any(result[k] for k in ('sourcePbfReads', 'networkRequests', 'applicationDbReads', 'countryCostsBuilt', 'modelChanged', 'etaQualified', 'vercelQualified'))
    return {'targetLinuxCostControls': 10, 'directedPrimitiveCostsExactlyMatched': 218666,
            'contractedArcSumsAndTicksExactlyMatched': 86517, 'countryCostsBuilt': False,
            'scope': 'Full source geometry and original integer-ms/125ms conventions on captured data, not country/app/ETA admission.',
            'reads': 'Small mirrored evidence and repository code only.'}


if __name__ == '__main__':
    print(json.dumps(verify()))
