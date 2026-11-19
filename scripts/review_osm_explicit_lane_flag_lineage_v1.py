"""Read-only selected-way flag lineage review; no coordinates or graph builder."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_car_policy_v2 import way_policy as original_policy
from coarse_osm_car_conditional_speed_v1 import POLICY, way_policy as current_policy
from coarse_osm_car_explicit_lanes_v1 import way_policy as proposed_policy
from coarse_osm_conditional_fact_io_v1 import Rows
from coarse_osm_conditional_records_v1 import read_records
from inventory_osm_lane_metadata_v1 import sha

REASONS=(None,'outside-major-profile','vehicle-ferry','access','area-ford-driveway-parking','conditional-or-way-restriction','lane-access','unsupported-oneway','unsupported-speed','directional-access')


def flags(policy,role):
    directions=int(policy.forward is not None)|(int(policy.backward is not None)<<1)
    defaults=int(policy.forward_default)|(int(policy.backward_default)<<1)
    return directions|(defaults<<2)|(role<<4)|(REASONS.index(policy.reason)<<8)


def run(recipe,pin):
    began=time.monotonic();repo=Path(__file__).resolve().parents[1]
    assert sha(recipe)==pin;plan=json.loads(recipe.read_bytes())
    assert plan['output']=='data/coarse-quality/us-osm-explicit-lane-flag-lineage-v1'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+104857600+8388608<72*1024**3
    for name,expected in plan['bindings'].items():assert sha(repo/name)==expected,name
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def check():
        assert time.monotonic()-began<120
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<4*1024**3
    try:
        catalog=json.loads((repo/plan['catalog']).read_bytes())['views']['country']
        pins={Path(dest).name:pin for dest,pin in catalog['files'].items() if Path(dest).name.startswith('ways-')}
        # A virtual roster selects the complete current way group; source files
        # share the same real output root in this closed conditional overlay.
        roots={str(Path(v['source']).parent.parent) for v in pins.values()};assert len(roots)==1
        roster={'cost-facts/'+name:{'bytes':v['bytes'],'sha256':v['sha256']} for name,v in pins.items()}
        source=Rows(repo/roots.pop(),roster,'ways','<QddII',check)
        records=list(read_records(repo/plan['records']));assert len(records)==3292
        assert all(r['type']=='way' for r in records)
        counts=Counter();mismatches=[];cursor=previous=0
        try:
            assert len(source)==4227238
            for i in range(len(source)):
                if i%8192==0:check()
                row=source[i];assert row[0]>previous;previous=row[0]
                if cursor==len(records) or row[0]<records[cursor]['id']:continue
                record=records[cursor];assert row[0]==record['id'];tags=record['tags']
                original,current,proposed=original_policy(tags),current_policy(tags),proposed_policy(tags)
                assert current.reason=='lane-access' and proposed.reason is None
                assert original.reason in ('conditional-or-way-restriction','lane-access')
                role=POLICY['roles'].index(tags['highway'])
                expected=flags(original,role);assert row[3]==expected and row[1:3]==(0.,0.)
                counts['original/'+str(original.reason)]+=1;counts['current/'+str(current.reason)]+=1
                if row[3]!=flags(current,role):
                    mismatches.append({'id':row[0],'tags':tags,'originalPolicy':asdict(original),
                                       'currentPolicy':asdict(current),'proposedPolicy':asdict(proposed),
                                       'storedFlags':row[3],'expectedOriginalFlags':expected,
                                       'expectedCurrentFlags':flags(current,role)})
                    assert len(mismatches)<=32
                cursor+=1
            assert cursor==len(records);source.verify_unchanged()
        finally:source.close()
        assert sha(repo/plan['records'])==plan['bindings'][plan['records']]
        report={'status':'all_selected_lane_way_source_flag_lineage_verified','recipeSha256':pin,
                'wayRowsVisited':4227238,'selectedWaysChecked':cursor,'counts':dict(counts),
                'storedFlagsMatchOriginalSourcePolicy':True,'storedFlagsDifferFromCurrentRejectedPolicy':len(mismatches),
                'mismatches':mismatches,'sourceRowsModified':0,'coordinateReads':0,'sourcePbfReads':0,
                'graphConstructors':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
                'hostSecondsIncludingBindingsWayReadAndPolicyReview':time.monotonic()-began,
                'scope':'Read-only captured changed-tag list and complete current country WAY group only. Existing conditional overlay normalized newly eligible ways but kept other original negative-reason flags. Every3292new lane candidate matches its ORIGINAL raw-tag source-policy flags and zero prior direction prices;current classification independently remains lane-access. Differences are historical stored labels,not changed source data or permission overrides. No coordinates/PBF/constructor/graph/query/provider/DB/app or speed fit. This reviews source lineage;it does not change the frozen eligibility policy.'}
        raw=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<=1048576
        (root/'report.json').write_bytes(raw);check()
        print(json.dumps({key:report[key] for key in ('status','wayRowsVisited','selectedWaysChecked','counts','storedFlagsDifferFromCurrentRejectedPolicy','hostSecondsIncludingBindingsWayReadAndPolicyReview')}))
    except BaseException as error:
        (root/'failure.json').write_text(json.dumps({'error':repr(error),'hostSeconds':time.monotonic()-began})+'\n');raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin')
    args=parser.parse_args();run(args.recipe,args.pin)
