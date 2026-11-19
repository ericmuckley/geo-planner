"""Recompute the one fixed-witness sensitivity; no model or large input reads."""
from fractions import Fraction
import json
import math
from statistics import mean

from verify_incomplete_node_diagnosis_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();plan=load(HERE/'default-timing-sensitivity-plan-v1.json')
    for name,pin in plan['bindings'].items(): assert sha(REPO/name)==pin,name
    review=load(HERE/'default-timing-source-review-v1.json')
    assert plan['policy']==review['policy']
    assert not review['hostedSettingsProved'] and not review['speedLimitHandlerResourceReviewComplete']
    assert plan['policy']['explicitEstimatedSpeedRatio']==[1,1]
    old=plan['policy']['currentDefaultsKph'];new=plan['policy']['proposedDefaultsKph']
    assert new==dict(motorway=100,motorway_link=60,trunk=85,trunk_link=60,primary=65,primary_link=50,secondary=60,secondary_link=50,tertiary=50,tertiary_link=40)
    attrs={r['id']:r for r in load(REPO/plan['attributes'])['rows']}
    diagnosis={r['id']:r for r in load(REPO/plan['diagnosis'])['rows']}
    candidate={r['id']:r for r in load(REPO/plan['candidate'])['rows']}
    screen=load(REPO/plan['output']);assert screen['recipeSha256']==sha(HERE/'default-timing-sensitivity-plan-v1.json')
    assert set(attrs)==set(diagnosis)==set(candidate)=={r['id']for r in screen['rows']} and len(attrs)==83
    for row in screen['rows']:
        source=attrs[row['id']];parts=diagnosis[row['id']]['components']
        ticks=Fraction(sum(parts.values())-parts['roadTravelTicks'])
        for key,group in source['groups'].items():
            role,kind=key.split('/')
            assert kind in ('default','tagged') and role in old
            if kind=='default': assert group['speedMinKph']==group['speedMaxKph']==old[role]
            ticks+=group['ticks']*(Fraction(old[role],new[role]) if kind=='default' else 1)
        assert row['currentMinutes']==sum(parts.values())/480==candidate[row['id']]['candidate']['pointMinutes']
        assert math.isclose(row['fixedWitnessSensitivityMinutes'],float(ticks/480),abs_tol=1e-10)
        assert math.isclose(row['minutesRemoved'],row['currentMinutes']-float(ticks/480),abs_tol=1e-10)
    for key,selected,record in [('overall',screen['rows'],screen['overall']),*[(s,[r for r in screen['rows']if r['set']==s],screen['sets'][s]) for s in ('original','regional','frontier')]]:
        value=mean(abs(r['fixedWitnessSensitivityMinutes']-r['referenceMinutes'])for r in selected)
        assert math.isclose(value,record['fixedWitnessSensitivityMeanAbsoluteMinutes'],abs_tol=1e-10)
    assert screen['modelQueries']==screen['providerRequests']==screen['newMaps']==0
    assert not screen['policyActivated'] and not screen['originalGatesChanged'] and not screen['isCandidateEvaluation']
    return {**result,'status':'one_published_base_default_continuous_witness_sensitivity_verified',
            'fixedWitnessSensitivityMeanAbsoluteMinutes':screen['overall']['fixedWitnessSensitivityMeanAbsoluteMinutes'],
            'currentCandidateMeanAbsoluteMinutes':screen['overall']['currentMeanAbsoluteMinutes'],
            'newCandidateEvaluation':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
