"""Compare all frozen cases honestly, preserving old/new missing routes separately."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def review(previous,current):
    def indexed(report):
        rows=report['rows']; assert len(rows)==83
        result={row['id']:row for row in rows}; assert len(result)==83
        for row in rows:
            value=row['candidate']['pointMinutes']
            assert value is None or isinstance(value,(int,float)) and math.isfinite(value) and value>=0
            assert math.isfinite(row['referenceMinutes'])
        return result
    before,after=indexed(previous),indexed(current); assert before.keys()==after.keys()
    for key in before:
        for field in ['origin','destination','budgetMinutes','referenceMinutes','valhallaMinutes','set','baseline']:
            assert before[key].get(field)==after[key].get(field),(key,field)
    finite=lambda rows:[key for key,row in rows.items() if row['candidate']['pointMinutes'] is not None]
    old_ids=set(finite(before)); new_ids=set(finite(after)); common=sorted(old_ids&new_ids)
    def summary(rows,ids):
        missing=[key for key in ids if rows[key]['candidate']['pointMinutes'] is None]
        errors=[abs(rows[key]['candidate']['pointMinutes']-rows[key]['referenceMinutes']) for key in ids if rows[key]['candidate']['pointMinutes'] is not None]
        return {'requestedCases':len(ids),'finiteCases':len(errors),'unavailableIds':sorted(missing),
                'allRequestedFinite':not missing,'meanAbsoluteMinutes':sum(errors)/len(errors) if errors and not missing else None}
    rows=[]
    for key in before:
        old=before[key]['candidate']['pointMinutes']; new=after[key]['candidate']['pointMinutes']
        rows.append({'id':key,'set':after[key]['set'],'previousMinutes':old,'currentMinutes':new,
                     'referenceMinutes':after[key]['referenceMinutes'],'changeMinutes':None if old is None or new is None else new-old,
                     'previousClassification':before[key]['candidate']['classification'],
                     'currentClassification':after[key]['candidate']['classification']})
    return {'originalCases':83,'previousFinite':len(old_ids),'currentFinite':len(new_ids),
            'recoveredIds':sorted(new_ids-old_ids),'newlyUnavailableIds':sorted(old_ids-new_ids),
            'stillUnavailableIds':sorted(before.keys()-new_ids),'all83':{'previous':summary(before,sorted(before)),'current':summary(after,sorted(after))},
            'samePreviousFiniteSet':{'previous':summary(before,sorted(old_ids)),'current':summary(after,sorted(old_ids))},
            'bothFiniteDiagnosticOnly':{'previous':summary(before,common),'current':summary(after,common)},
            'existingFinitePointTimesChanged':sum(abs(before[key]['candidate']['pointMinutes']-after[key]['candidate']['pointMinutes'])>1e-10 for key in common),
            'rows':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('previous',type=Path);parser.add_argument('current',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
    old=args.previous.read_bytes();new=args.current.read_bytes();current=json.loads(new);r=review(json.loads(old),current)
    r['frozenNumericalGatesPassed']=current['numericalGatesPassed'];r['frozenNumericalGates']=current['gates']
    r.update(status='complete_frozen_water_candidate_all_case_comparison',inputs={str(args.previous):hashlib.sha256(old).hexdigest(),str(args.current):hashlib.sha256(new).hexdigest()},producerSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),providerRequests=0,modelQueries=0,policyChanged=False,scope='All83 original IDs/references/baseline semantics retained. Missing cases make a requested-set mean null; both-finite subset is diagnostic only, never accuracy acceptance. Observed development data, not holdout/national/traffic truth. No model or app change.')
    with args.output.open('x') as stream:json.dump(r,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ['rows','inputs','scope']}))


if __name__=='__main__':main()
