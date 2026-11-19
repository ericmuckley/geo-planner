"""All excluded major ways versus same-epoch cached tags; unknowns never infer permission."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sqlite3
import sys
import time

from coarse_osm_country_screen_v1 import owned_usage
from coarse_osm_source_gap_way_causes_v1 import way_cause
from coarse_timing_input import require

REPO=Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('pin');args=parser.parse_args()
    began=time.monotonic();recipe=REPO/args.plan;require(sha(recipe)==args.pin,'Way tags recipe binding');plan=json.loads(recipe.read_bytes())
    require(plan['output']=='data/coarse-quality/us-osm-source-gap-way-tags-v1','Way tags exact output')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['activeCandidateOwnedReserveBytes']+67108864<72*1024**3,'Way tags includes active candidate reservation')
    for name,pin in plan['bindings'].items():require(not name.endswith(('.pbf','/001.bin')) and sha(REPO/name)==pin,'Way tags readonly binding: '+name)
    active=json.loads((REPO/plan['activeCandidateRecipe']).read_bytes())
    require(active['output']=='data/coarse-quality/us-osm-passable-node-evaluation-v1' and plan['activeCandidateOwnedReserveBytes']==active['maxOwnedBytes']==268435456,'Reserve the complete active candidate output cap')
    first=json.loads((REPO/plan['cacheSourcePlan']).read_bytes())['source'];second=json.loads((REPO/plan['currentSourcePlan']).read_bytes())['source']
    require(first['sha256']==second['sha256'] and first['bytes']==second['bytes'],'Same original source epoch')
    root=REPO/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def check():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        require(time.monotonic()-began<300 and rss<536870912 and owned_usage(root)['conservativeAllocatedBytes']<67108864,'Way tags host deadline/RSS/owned cap')
        return rss
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=1048576,'Way tags small report bound')
        with (root/name).open('xb') as stream:stream.write(raw)
    try:
        path=(REPO/plan['cacheDatabase']).resolve();before=path.stat()
        db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
        known=[];unknown=[];reasons=Counter();classes=Counter();previous=rows=raw_bytes=0;digest=hashlib.sha256()
        try:
            with gzip.open(REPO/plan['sourceGeometry'],'rb') as stream:
                while raw:=stream.readline(4194305):
                    if rows%256==0:check()
                    require(len(raw)<=4194304 and raw.endswith(b'\n') and rows<52743,'Complete bounded original source geometry record')
                    rows+=1;raw_bytes+=len(raw);digest.update(raw);row=json.loads(raw)
                    identity=row['sourceWay'];require(previous<identity,'Unique sorted source ways');previous=identity
                    found=db.execute("SELECT id,raw FROM objects WHERE kind='way' AND id=?",(identity,)).fetchone()
                    raw_way=None
                    if found is not None:
                        require(found[0]==identity and len(found[1])<=4194304,'Bound cached original way')
                        raw_way=json.loads(found[1])
                    result=way_cause(row,raw_way)
                    if raw_way is None:unknown.append(str(identity))
                    else:
                        known.append(result);reasons[str(result['currentRawPolicy']['reason'])]+=1
                        classes['base-eligible-fallback-closed' if row['baseEligible'] else 'base-ineligible']+=1
        finally:db.close()
        require(rows==52743 and raw_bytes==plan['geometryRawBytes'] and digest.hexdigest()==plan['geometryRawSha256'],'Every selected geometry record/raw seal checked')
        require(path.stat()==before and sha(path)==plan['bindings'][plan['cacheDatabase']] and path.stat()==before,'Readonly source cache unchanged')
        evidence={'knownWays':known,'unknownRawWayIds':unknown}
        raw=(json.dumps(evidence,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();require(len(raw)<=16777216,'Complete cached-way evidence cap')
        packed=gzip.compress(raw,mtime=0)
        with (root/'way-evidence.json.gz').open('xb') as stream:stream.write(packed)
        save('report.json',{'status':'all_excluded_major_way_cached_tag_coverage_audited','recipeSha256':args.pin,
             'allSelectedSourceWays':rows,'sourceCacheWayQueries':rows,'rawWaysKnown':len(known),'rawWaysUnknown':len(unknown),
             'knownCurrentReasonCounts':dict(reasons),'knownSelectionClassCounts':dict(classes),
             'sameOriginalSourceSha256':first['sha256'],
             'artifact':{'file':'way-evidence.json.gz','bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest(),'rawBytes':len(raw),'rawSha256':hashlib.sha256(raw).hexdigest()},
             'sourcePbfReads':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
             'sourcePermissionsOrPricesChanged':False,'appActivated':False,
             'hostSecondsIncludingBindingsAllSourceWayQueriesAndPolicyReplay':time.monotonic()-began,'hostMaximumRssBytes':check(),
             'scope':'All52743excluded major ways checked against same-epoch readonly original source cache, not selected places. All cached known raw tag policies independently reconcile current eligibility; stored original reason codes remain separate from current raw reasons. Final fallback closure is independent of base-way eligibility. Every missing raw way remains unknown; no permission, road identity/corridor, corrected model, accuracy or app inference. Includes separate active full-map candidate output reservation under unchanged72GiBaggregate. Host512MiBRSS/300s/64MiBowned, not protected or cloud evidence.'})
    except BaseException as error:
        save('failure.json',{'status':'excluded_way_tag_inventory_stopped','error':repr(error)});raise


if __name__=='__main__':main()
