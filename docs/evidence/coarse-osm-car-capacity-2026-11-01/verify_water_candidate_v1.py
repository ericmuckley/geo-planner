"""Portable rejected full83/35 mask-candidate evidence, no routing/producer replay."""
import json
from verify_water_country_profile_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous(); report=stage('water-country-evaluation')
    assert report['status']=='completed_fixed_water_mask_candidate_screen'
    assert report['originalCases']==83 and report['valhallaCases']==35 and len(report['rows'])==83
    assert not report['numericalGatesPassed'] and not report['candidateAdmitted']
    assert report['gates']['all83Finite'] and not report['gates']['all35OlderShaded']
    assert report['overall']['candidate']['pairedFinite']==report['overall']['baseline']['pairedFinite']==83
    assert abs(report['overall']['candidate']['meanAbsoluteMinutes']-32.614352409638556)<1e-10
    assert abs(report['overall']['baseline']['meanAbsoluteMinutes']-29.257418754386766)<1e-10
    assert report['productionDisplays']==37 and report['diagnosticDisplays']==len(report['phases'])==21
    assert report['unsupportedSourceCases']==report['providerRequests']==0
    assert report['roadMonotonicComparisons']==78 and not report['roadArrivalRegressions']
    assert report['validatedInitialChoices']==10256 and report['waterPacketObservationsCompared']==1002
    assert report['parityOriginComparisons']==6
    assert report['retainedBackingBytes']==157130033 and report['retainedBackingGatePassed']
    assert report['afterLoad']['arrayBuffers']==report['afterQueries']['arrayBuffers']==157206283
    scratch=max(item['stats']['maximumBackingBufferBytes'] for phase in report['phases'] for item in [phase['diagnostic'],*phase['productions']])
    assert scratch==59257215<67108864
    review=load(HERE/'water-candidate-review-v1.json')
    for name,pin in review['inputs'].items():assert sha(REPO/name)==pin,name
    assert sha(REPO/'scripts/review_osm_water_candidate_v1.py')==review['producerSha256']
    assert review['previousFinite']==80 and review['currentFinite']==83 and len(review['recoveredIds'])==3
    assert not review['newlyUnavailableIds'] and not review['stillUnavailableIds']
    assert review['existingFinitePointTimesChanged']==6
    assert review['all83']['previous']['meanAbsoluteMinutes'] is None
    old=review['samePreviousFiniteSet'];assert old['previous']['requestedCases']==old['current']['requestedCases']==80
    assert abs(old['previous']['meanAbsoluteMinutes']-33.7261875)<1e-10
    assert abs(old['current']['meanAbsoluteMinutes']-33.77084895833333)<1e-10
    assert review['frozenNumericalGates']==report['gates'] and not review['frozenNumericalGatesPassed']
    closed=load(HERE/'water-country-evaluation-closed-v1.json')
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==5375090688
    return {**result,'waterFullAccuracyMeasured':True,'waterCandidateFiniteRoutes':83,
            'waterCandidateRecoveredRoutes':3,'waterCandidateAll83MeanErrorMinutes':32.614352409638556,
            'waterV9All83MeanErrorMinutes':29.257418754386766,'waterCandidateSame80MeanErrorMinutes':33.77084895833333,
            'waterCandidateMaximumQueryBackingBytes':scratch,'waterCandidateRetainedBackingBytes':157130033,
            'newUniqueClosedAllocationBytes':total,'uniqueClosedRoots':164,
            'waterCandidateNumericalGatesPassed':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
