"""Reconcile every collected way with current closures, no new model/source query."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from coarse_osm_current_way_exclusions_v1 import classify_inventory, reconcile_closures
from coarse_osm_full_monitor_v1 import owned_usage

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(recipe,pin):
    began=time.monotonic();assert sha(recipe)==pin
    plan=json.loads(recipe.read_bytes())
    assert plan['output']=='data/coarse-quality/us-osm-current-way-exclusions-v1'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864<72*1024**3
    assert not any(n.endswith(('.pbf','/001.bin','.sqlite')) for n in plan['bindings'])
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    root=REPO/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<=1048576
        with (root/name).open('xb')as stream:stream.write(raw)
    def check():
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        assert time.monotonic()-began<300 and peak<536870912 and owned_usage(root)['conservativeAllocatedBytes']<67108864
        return peak
    def unpack(name,maximum):
        with gzip.open(REPO/plan[name],'rb') as stream:raw=stream.read(maximum+1)
        assert len(raw)<=maximum;return json.loads(raw)
    try:
        source=unpack('sourceEvidence',48*1048576)
        assert source['selectedWays']==52743 and not source['unknownRawWayIds']
        old=unpack('oldClosureEvidence',16*1048576)
        assert len(old['allClosedWayContributorIds'])==29657
        ports=unpack('sourcePorts',16*1048576)
        assert len(ports['rows'])==7480 and len({r['sourceRelationId']for r in ports['rows']})==7480
        converted={int(r['sourceRelationId'])for r in ports['rows']if r['status']=='source-ports-supported'}
        assert len(converted)==1331
        relations={r['sourceRelation']:r for r in old['closingRelations']}
        assert len(relations)==len(old['closingRelations']) and converted<=relations.keys()
        raw=(REPO/plan['currentClosures']).read_bytes();assert len(raw)==27421*8
        ids=[v[0]for v in struct.iter_unpack('<Q',raw)];assert ids==sorted(set(ids))
        current=set(ids);contributors=reconcile_closures(old['allClosedWayContributorIds'],converted,current);check()
        rows,counts,reasons,lane_shapes=classify_inventory(source['wayEvidence'],current,contributors,relations);check()
        assert len(rows)==52743 and counts['retained-now']==2236
        artifact=json.dumps({'rows':rows,'allCurrentClosedWayContributorIds':contributors},sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        assert len(artifact)<=32*1048576
        packed=gzip.compress(artifact,mtime=0)
        with (root/'current-exclusions.json.gz').open('xb')as stream:stream.write(packed)
        access=Counter();lane_status=Counter();kinds=Counter()
        for key,row in rows.items():
            if row['baseReason']=='access':
                tags=source['wayEvidence'][key]['rawTags']
                for k in ('motorcar','motor_vehicle','vehicle','access'):
                    if k in tags:access[k+'='+tags[k]]+=1
            if row['baseReason']=='lane-access':lane_status[str(row['laneStatus'])]+=1
            if row['currentFallbackClosed']:
                for kind in row['closingKinds']:kinds[kind]+=1
        save('report.json',dict(status='all_original_way_exclusions_current_closure_membership_audited',recipeSha256=sha(recipe),
             sourceSelectedWays=52743,knownOriginalWayTags=52743,unknownOriginalWayTags=0,
             oldGlobalClosureIds=29657,currentGlobalClosureIds=27421,convertedRelationContributors=1331,
             allCurrentClosureContributorUnionsExact=True,categories=counts,baseReasons=reasons,laneShapes=lane_shapes,
             laneStatuses=dict(lane_status),currentSelectedClosureKinds=dict(kinds),
             commonAccessTagObservations=dict(access.most_common(30)),
             artifact=dict(file='current-exclusions.json.gz',bytes=len(packed),sha256=hashlib.sha256(packed).hexdigest(),rawBytes=len(artifact),rawSha256=hashlib.sha256(artifact).hexdigest()),
             hostSecondsIncludingBindingsAllTagAndCurrentClosureJoins=time.monotonic()-began,hostMaximumRssBytes=check(),
             sourcePbfReads=0,modelQueries=0,providerRequests=0,applicationDbReads=0,policyChanged=False,appActivated=False,
             scope='All52743original excluded-major selection IDs with complete original tags, independent base eligibility and all27421current global closure contributor unions. Removes only1331already source-qualified conditional-node contributors, preserving independent shared closures. Old selection flags remain historical;2236now-retained roads are explicit, not miscalled current exclusions. Categories/tag-shape/access distributions are observations, never permission/causal corridor or new routing/accuracy proof. Original source/legal/currentestimated prices/gates andv9stay. Host512MiBRSS/300s/64MiBowned metadata work under unchanged72GiBaggregate, not cgroup/cloud/query latency.'))
    except BaseException as error:
        save('failure.json',dict(status='current_way_exclusion_inventory_stopped',error=repr(error)));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin');args=parser.parse_args();run(args.recipe,args.pin)
