"""Bounded captured-source lane-policy comparison; no graph or coordinate read."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import resource
import sqlite3
import sys
import time

from coarse_osm_backbone_v1 import MAJOR
from coarse_osm_car_conditional_speed_v1 import way_policy as previous_policy
from coarse_osm_car_explicit_lanes_v1 import classify_way
from inventory_osm_lane_metadata_v1 import identity, sha


def run(recipe, pin):
    began=time.monotonic();repo=Path(__file__).resolve().parents[1]
    assert sha(recipe)==pin
    plan=json.loads(recipe.read_bytes())
    assert plan['output']=='data/coarse-quality/us-osm-explicit-lanes-capture-v1'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['maxOwnedBytes']<72*1024**3
    for name,expected in plan['bindings'].items():assert sha(repo/name)==expected,name
    source=repo/plan['database'];before=identity(source)
    assert source.is_file() and not source.is_symlink() and source.stat().st_size==plan['databaseBytes']==336826368
    assert sha(source)==plan['databaseSha256']
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def check():
        assert time.monotonic()-began<plan['hostSeconds']==120
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<4*1024**3
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<=1048576
        with (root/name).open('xb') as stream:stream.write(raw)
    try:
        counts=Counter();rows=[];seen=last=0
        db=sqlite3.connect(source.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
            assert db.execute("SELECT count(*) FROM objects WHERE kind='way'").fetchone()[0]==239253
            query="SELECT id,json_extract(CAST(raw AS TEXT),'$.tags') FROM objects WHERE kind='way' AND json_extract(CAST(raw AS TEXT),'$.tags.highway') IN ("+','.join('?' for _ in MAJOR)+") ORDER BY id"
            for way,encoded in db.execute(query,MAJOR):
                assert last<way;last=way;seen+=1;assert seen<=28995
                assert isinstance(encoded,str) and len(encoded.encode())<=4194304
                tags=json.loads(encoded);assert isinstance(tags,dict) and len(tags)<=65536
                assert all(isinstance(k,str) and isinstance(v,str) for k,v in tags.items())
                preserved=json.dumps(tags,sort_keys=True)
                old=asdict(previous_policy(tags));explanation=classify_way(tags);new=asdict(explanation['policy'])
                assert json.dumps(tags,sort_keys=True)==preserved
                counts['before/'+str(old['reason'])]+=1;counts['after/'+str(new['reason'])]+=1
                if old['reason'] is None:
                    assert old==new;counts['oldEligibleRetainedExactly']+=1
                if old!=new:
                    assert old['reason']=='lane-access' and new['reason'] is None
                    assert explanation['explicitOrdinaryLaneIndices'] and explanation['acceptedLaneKeys']
                    scoped={key:value for key,value in tags.items() if key not in explanation['acceptedLaneKeys']}
                    assert new==asdict(previous_policy(scoped))
                    assert (new['forward'] is None)!=(new['backward'] is None)
                    counts['newEligible']+=1
                if old['reason']=='lane-access':
                    rows.append({'kind':'way','id':way,'tags':tags,'before':old,'after':new,
                                 'eligibilityGained':old!=new,
                                 **{key:value for key,value in explanation.items() if key!='policy'}})
                    assert len(rows)<=1000
                else:assert old==new
                if seen%1024==0:check()
        finally:db.close()
        assert seen==28995 and len(rows)==32
        assert identity(source)==before and sha(source)==plan['databaseSha256'] and identity(source)==before
        # Preserve all formerly rejected lane forms, including unchanged fallbacks.
        save('lane-records.json',rows)
        report={'status':'captured_explicit_ordinary_lane_policy_comparison_complete',
                'recipeSha256':pin,'majorWaysCompared':seen,'capturedSourceWayRows':239253,
                'counts':dict(counts),'laneRejectedRecords':len(rows),
                'recordsSha256':sha(root/'lane-records.json'),'immutableSourcePreserved':True,
                'sourcePbfReads':0,'coordinateReads':0,'graphConstructors':0,'routingQueries':0,
                'providerRequests':0,'applicationDbOperations':0,'engineOrProductionChanged':False,
                'hostSecondsIncludingBindingsSqliteComparisonAndSourceHashes':time.monotonic()-began,
                'scope':'Captured saved-source tags only. All old eligible decisions/prices/directions exact;changes only from lane-access rejection to a common explicit yes column on a static one-way road,with unchanged scoped base policy. Every32former lane rejection retained,including fallbacks. Readonly immutable research SQLite,not application DB. No lane-change/turn-lane/connectivity proof,graph/native parity,national coverage,causal detour,ETA,accuracy or app admission. Host RSS/deadline checks do not establish cgroup/CPU/swap admission.'}
        save('report.json',report);check();print(json.dumps(report))
    except BaseException as error:
        save('failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin')
    args=parser.parse_args();run(args.recipe,args.pin)
