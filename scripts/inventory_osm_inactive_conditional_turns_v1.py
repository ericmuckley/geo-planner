"""One fixed-profile inactive-rule metadata projection, never graph or model execution."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from coarse_osm_current_way_exclusions_v1 import reconcile_closures
from coarse_osm_inactive_conditional_turns_v1 import POLICY, effects

REPO=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(recipe,pin):
    began=time.monotonic();assert sha(recipe)==pin;plan=json.loads(recipe.read_bytes());assert plan['policy']==POLICY
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+104857600<72*1024**3
    for name,pin in plan['bindings'].items():assert not name.endswith(('.pbf','/001.bin','.sqlite')) and sha(REPO/name)==pin,name
    def read(name,cap):
        with gzip.open(REPO/plan[name],'rb')as stream:raw=stream.read(cap+1)
        assert len(raw)<=cap;return json.loads(raw)
    metadata=read('metadata',16*1048576)['candidates'];ports=read('sourcePorts',16*1048576)
    assert len(metadata)==len(ports['rows'])==7480
    classified=effects(metadata,ports['rows'])
    old=read('oldClosures',16*1048576);current=read('currentExclusions',32*1048576)['rows']
    assert len(current)==52743
    rules={r['source']['id']:r['source']for r in metadata};closing={r['sourceRelation']:r for r in old['closingRelations']}
    assert rules.keys()<=closing.keys()
    for identity,source in rules.items():assert source['tags']==closing[identity]['rawTags'] and source['members']==closing[identity]['sourceMembers']
    raw=(REPO/plan['currentClosureIds']).read_bytes();assert len(raw)==27421*8
    current_ids={r[0]for r in struct.iter_unpack('<Q',raw)};assert len(current_ids)==27421
    baseline=reconcile_closures(old['allClosedWayContributorIds'],classified['represented'],current_ids)
    converted=classified['represented']|classified['inactive']
    proposed={int(way)for way,ids in old['allClosedWayContributorIds'].items()if set(ids)-converted}
    assert proposed<=current_ids
    reopened=current_ids-proposed
    major={int(k)for k,r in current.items()if r['baseEligible'] and int(k)in reopened}
    assert all(current[str(i)]['currentFallbackClosed'] for i in major)
    report=dict(status='inactive_conditional_fixed_profile_metadata_projection_complete',recipeSha256=sha(recipe),
                metadataRules=7480,representedRules=len(classified['represented']),inactiveRules=len(classified['inactive']),
                fallbackRules=len(classified['fallback']),currentGlobalClosedWays=27421,proposedGlobalClosedWays=len(proposed),
                proposedGlobalReopenedWays=len(reopened),proposedBaseEligibleMajorReopenedWays=len(major),
                allIndependentUnconvertedContributorUnionsExact=True,
                inactiveSourceRelationIds=[str(i)for i in sorted(classified['inactive'])],
                proposedGlobalClosureIds=[str(i)for i in sorted(proposed)],
                proposedMajorReopenedWayIds=[str(i)for i in sorted(major)],
                baselineClosureContributorRows=len(baseline),
                sourcePbfReads=0,sourceConstructorExecutions=0,modelQueries=0,providerRequests=0,
                nativeCompilerExecuted=False,sourcePolicyActivated=False,accuracyOrAppAccepted=False,
                hostSecondsIncludingBindingsAllMetadataAndContributorProjection=time.monotonic()-began,
                hostMaximumRssBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
                scope=plan['scope'])
    assert report['hostSecondsIncludingBindingsAllMetadataAndContributorProjection']<120 and report['hostMaximumRssBytes']<536870912
    raw=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<8*1048576
    with (REPO/plan['output']).open('xb')as stream:stream.write(raw)
    print(json.dumps({k:v for k,v in report.items()if not k.endswith('Ids')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recipe',type=Path);p.add_argument('pin');a=p.parse_args();run(a.recipe,a.pin)
