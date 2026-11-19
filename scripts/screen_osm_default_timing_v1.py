"""One frozen all83 continuous witness sensitivity, never routing or fitted costs."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
import time

from coarse_osm_default_timing_v1 import POLICY, continuous_path_ticks


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(recipe, pin):
    began = time.monotonic(); repo = Path(__file__).resolve().parents[1]
    assert sha(recipe) == pin
    plan = json.loads(recipe.read_bytes())
    assert plan['policy'] == POLICY
    assert plan['priorReserveBytes'] + plan['newClosedAllocationBytes'] + plan['metadataScratchReserveBytes'] < 72 * 1024**3
    for name, expected in plan['bindings'].items(): assert sha(repo/name) == expected, name
    candidate = json.loads((repo/plan['candidate']).read_bytes())
    diagnosis = json.loads((repo/plan['diagnosis']).read_bytes())
    attributes = json.loads((repo/plan['attributes']).read_bytes())
    current = {r['id']:r for r in candidate['rows']}
    sources = {r['id']:r for r in attributes['rows']}
    assert len(current) == len(sources) == len(diagnosis['rows']) == 83 and not diagnosis['unavailable']
    rows = []
    for row in diagnosis['rows']:
        assert time.monotonic() - began < 60
        sample = current[row['id']]; source = sources[row['id']]
        before = sum(row['components'].values())/480
        assert before == row['candidateMinutes'] == sample['candidate']['pointMinutes'] == source['candidateMinutes']
        after = continuous_path_ticks(row['components'], source['groups'])/480
        rows.append(dict(id=row['id'],set=row['set'],referenceMinutes=row['referenceMinutes'],valhallaMinutes=sample['valhallaMinutes'],
                         baselineMinutes=sample['baseline']['pointMinutes'],currentMinutes=before,fixedWitnessSensitivityMinutes=after,
                         minutesRemoved=before-after,kind=row['kind']))
    def summarize(items, reference='referenceMinutes'):
        assert items and all(r[reference] is not None for r in items)
        return dict(cases=len(items),baselineMeanAbsoluteMinutes=mean(abs(r['baselineMinutes']-r[reference]) for r in items),
                    currentMeanAbsoluteMinutes=mean(abs(r['currentMinutes']-r[reference]) for r in items),
                    fixedWitnessSensitivityMeanAbsoluteMinutes=mean(abs(r['fixedWitnessSensitivityMinutes']-r[reference]) for r in items),
                    meanMinutesRemoved=mean(r['minutesRemoved'] for r in items))
    report = dict(status='published_base_defaults_all83_fixed_witness_sensitivity_complete',recipeSha256=pin,rows=rows,
                  overall=summarize(rows),sets={s:summarize([r for r in rows if r['set']==s]) for s in ('original','regional','frontier')},
                  valhalla={s:summarize([r for r in rows if r['set']==s],'valhallaMinutes') for s in ('original','regional')},
                  modelQueries=0,providerRequests=0,newMaps=0,policyActivated=False,originalGatesChanged=False,isCandidateEvaluation=False,
                  hostSeconds=time.monotonic()-began,scope=plan['scope'])
    with (repo/plan['output']).open('x') as stream: json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({k:report[k] for k in ('status','overall','sets','valhalla','isCandidateEvaluation')}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recipe',type=Path);p.add_argument('pin');a=p.parse_args();run(a.recipe,a.pin)
