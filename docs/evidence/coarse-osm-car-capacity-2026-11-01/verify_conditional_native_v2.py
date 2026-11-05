"""Native parity with explicit interpretation of an inherited report label."""
import json
from verify_conditional_native_v1 import verify as previous
from verify_preparation_v1 import HERE,load,sha


def verify():
    result=previous();review=load(HERE/'conditional-native-scope-review-v1.json')
    assert sha(HERE/review['source'])==review['sourceSha256']
    assert load(HERE/review['source'])[review['inheritedField']]==review['inheritedValue']
    for name,pin in review['bindings'].items():assert sha(HERE/name)==pin
    assert review['allCapturedNativeAndNewPythonMatch'] and review['allOldPositiveDecisionsUnchanged']
    assert not review['allLegacyDecisionsUnchanged'] and review['legacyWayEligibilityChanges']==108 and review['legacyNodeEligibilityChanges']==0
    assert not review['producerChangedOrReplayed']
    return {**result,'conditionalNativeInheritedScopeLabelCorrected':True,'conditionalNativeAllLegacyDecisionsUnchanged':False}


if __name__=='__main__':print(json.dumps(verify()))
