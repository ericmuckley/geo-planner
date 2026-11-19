"""One predeclared continuous tagged-speed sensitivity on current frozen roads."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(recipe,pin):
    began=time.monotonic();repo=Path(__file__).resolve().parents[1]
    assert sha(recipe)==pin;plan=json.loads(recipe.read_bytes())
    assert plan['taggedSpeedRatio']==[9,10] and plan['defaultSpeedRatio']==[1,1]
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']<72*1024**3
    for name,expected in plan['bindings'].items():assert sha(repo/name)==expected,name
    point=json.loads((repo/plan['pointReport']).read_bytes())
    diagnosis=json.loads((repo/plan['roadDiagnosis']).read_bytes())
    roads={r['id']:r for r in diagnosis['rows']};timings={r['id']:r for r in point['comparisons']}
    assert len(point['rows'])==len(timings)==83 and len(roads)==82 and len(diagnosis['unavailable'])==1
    rows=[]
    for sample in point['rows']:
        assert time.monotonic()-began<60
        key=sample['id'];timing=timings[key];road=roads.get(key)
        before=timing['bestRoadTicks'];local=timing['frozenLocalGridTicks'];added=0
        if before is None:
            assert road is None and key==diagnosis['unavailable'][0]['id']
            after=None
        else:
            assert road is not None and road['candidateMinutes']==before/480 and road['referenceMinutes']==sample['referenceMinutes']
            exposure=road['sourceSpeedExposure'];components=road['components']
            assert exposure['unknownTicks']==0 and exposure['explicitTicks']+exposure['defaultTicks']==components['roadTravelTicks']
            assert sum(components.values())==before
            # Continuous fixed-path elapsed-time sensitivity only. Macro tick
            # quantization, paid positions and new shortest paths are NOT repriced.
            added=exposure['explicitTicks']/9
            after=before+added
        current=min(v for v in (before,local) if v is not None)
        hypothetical=min(v for v in (after,local) if v is not None)
        assert current==timing['pointTicks'] and current/480==sample['candidate']['pointMinutes']
        rows.append(dict(id=key,set=sample['set'],budgetMinutes=sample['budgetMinutes'],referenceMinutes=sample['referenceMinutes'],
                         valhallaMinutes=sample['valhallaMinutes'],baselineMinutes=sample['baseline']['pointMinutes'],
                         roadUnavailable=before is None,currentRoadMinutes=None if before is None else before/480,
                         fixedRoadSensitivityMinutes=None if after is None else after/480,taggedTimeAddedMinutes=added/480,
                         frozenLocalGridMinutes=None if local is None else local/480,currentPointMinutes=current/480,
                         fixedPointSensitivityMinutes=hypothetical/480))
    assert len({r['id'] for r in rows})==83 and sum(r['roadUnavailable'] for r in rows)==1
    def summarize(items,reference='referenceMinutes'):
        assert items and all(r[reference] is not None for r in items)
        return dict(cases=len(items),baselineMaeMinutes=mean(abs(r['baselineMinutes']-r[reference]) for r in items),
                    currentPointMaeMinutes=mean(abs(r['currentPointMinutes']-r[reference]) for r in items),
                    fixedPointSensitivityMaeMinutes=mean(abs(r['fixedPointSensitivityMinutes']-r[reference]) for r in items),
                    meanPointTimeAddedMinutes=mean(r['fixedPointSensitivityMinutes']-r['currentPointMinutes'] for r in items))
    overall=summarize(rows);sets={s:summarize([r for r in rows if r['set']==s]) for s in ('original','regional','frontier')}
    means=dict(overall=overall['fixedPointSensitivityMaeMinutes']<=0.9*overall['baselineMaeMinutes'],
               frontier=sets['frontier']['fixedPointSensitivityMaeMinutes']<=0.9*sets['frontier']['baselineMaeMinutes'],
               original=sets['original']['fixedPointSensitivityMaeMinutes']<=sets['original']['baselineMaeMinutes'],
               regional=sets['regional']['fixedPointSensitivityMaeMinutes']<=sets['regional']['baselineMaeMinutes'])
    report=dict(status='one_external_lane_tagged90_frozen_road_point_sensitivity_complete',recipeSha256=pin,rows=rows,overall=overall,sets=sets,
                valhalla={s:summarize([r for r in rows if r['set']==s],'valhallaMinutes') for s in ('original','regional')},
                necessaryMeanGatesOnly=means,allNecessaryMeanGatesPass=all(means.values()),
                newRoutingQueries=0,newMaps=0,providerRequests=0,policyActivated=False,originalGatesChanged=False,isCandidateEvaluation=False,
                hostSeconds=time.monotonic()-began,
                scope='One predeclared externally reviewed9/10 tagged-speed ratio on ALL current frozen roadpaths. All83points/one roadnull and frozen localgrid retained;explicit source ticks alone scale continuously,defaults/signals/connectors/localgrid fixed. This is NOT exact primitive/macro re-quantization,paid-position repricing,new optima,access choices,new maps,166sums,shape/accuracy/app admission. Means are necessary diagnostic checks only;all original gates remain. No ratio sweep/fit/place rule/provider/PBF/constructor/DB/app change.')
    with (repo/plan['output']).open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({k:report[k] for k in ['status','overall','sets','necessaryMeanGatesOnly','isCandidateEvaluation']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin');args=parser.parse_args();run(args.recipe,args.pin)
