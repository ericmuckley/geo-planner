"""Attribute every current fallback-closed way to original source relation contributors."""
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_multiway_entry_v1 import multiway_rule
from coarse_osm_restriction_entry_v1 import entry_restriction
from coarse_timing_input import require


def contribution(element,single_decisions,multi_decisions):
    policy=restriction_policy(element)
    require(policy['status']=='closed-unsupported','Only original unsupported car relations')
    single=entry_restriction(element)
    if single is not None:
        status=single_decisions[element['id']]
        return (policy['memberWays'] if status==2 else []),'single-no-join' if status==2 else 'single-resolved-or-inactive','single'
    multi=multiway_rule(element)
    if multi is not None:
        status=multi_decisions[element['id']]
        return (policy['memberWays'] if status==2 else []),'multi-no-join' if status==2 else 'multi-resolved-or-inactive','multi'
    conditional=any(key.endswith(':conditional') for key in element['tags'])
    only=any(key.startswith('restriction') and value.startswith('only_') for key,value in element['tags'].items())
    return policy['memberWays'],'constant-conditional' if conditional else 'constant-static-only' if only else 'constant-other-static',None


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('pin');args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];began=time.monotonic();recipe=repo/args.plan
    require(sha(recipe)==args.pin,'Closure inventory recipe binding');plan=json.loads(recipe.read_bytes())
    require(plan['output']=='data/coarse-quality/us-osm-source-gap-closures-v1','Closure inventory exact output')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['activeCandidateOwnedReserveBytes']+67108864<72*1024**3,'Closure inventory reserves active full candidate')
    for name,pin in plan['bindings'].items():require(not name.endswith(('.pbf','/001.bin')) and sha(repo/name)==pin,'Closure inventory readonly input: '+name)
    active=json.loads((repo/plan['activeCandidateRecipe']).read_bytes());require(active['maxOwnedBytes']==plan['activeCandidateOwnedReserveBytes']==268435456,'Entire active candidate cap reserved')
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def check():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        require(time.monotonic()-began<300 and rss<536870912,'Closure inventory host deadline/RSS')
        return rss
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=1048576,'Closure inventory small record cap')
        with (root/name).open('xb') as stream:stream.write(raw)
    def decisions(key):
        raw=(repo/plan[key]).read_bytes();require(len(raw)%16==0 and len(raw)<=1600000,'Current decision byte bounds')
        values=list(struct.iter_unpack('<QII',raw));require(all(row[1] in (0,2,3) and (i==0 or values[i-1][0]<row[0]) for i,row in enumerate(values)),'Current complete sorted resolution decisions')
        return {identity:status for identity,status,_ in values}
    try:
        single=decisions('singleDecisions');multi=decisions('multiDecisions')
        raw=(repo/plan['closedWays']).read_bytes();require(len(raw)==29657*8,'Current final closure byte count')
        ordered=[row[0] for row in struct.iter_unpack('<Q',raw)];require(ordered==sorted(set(ordered)),'Current final closures sorted/unique');closed=set(ordered)
        by_way=defaultdict(list);by_kind=defaultdict(set);relation_counts=Counter();details=[];seen_single=set();seen_multi=set();count=previous=0;digest=hashlib.sha256()
        with (repo/plan['rawRelations']).open('rb') as stream:
            while line:=stream.readline(2097153):
                if count%256==0:check()
                require(len(line)<=2097152 and line.endswith(b'\n') and count<70376,'Complete bounded original raw relation')
                digest.update(line);element=json.loads(line);require(previous<element['id'],'Raw relation identity/order');previous=element['id'];count+=1
                ways,kind,branch=contribution(element,single,multi)
                if branch=='single':seen_single.add(element['id'])
                elif branch=='multi':seen_multi.add(element['id'])
                relation_counts[kind]+=1
                if ways:
                    require(set(ways)<=closed,'Every actual contributor belongs to current closed union')
                    details.append({'sourceRelation':element['id'],'closureKind':kind,'closedWays':[str(w) for w in ways],'rawTags':element['tags'],'sourceMembers':element['members']})
                    for identity in ways:by_way[str(identity)].append(element['id']);by_kind[kind].add(identity)
        require(count==70376 and digest.hexdigest()==plan['bindings'][plan['rawRelations']],'Complete original relation count/seal')
        require(seen_single==set(single) and seen_multi==set(multi),'Every current resolution decision classified once')
        require({int(w) for w in by_way}==closed,'ALL final closed ways have exactly the reconstructed contributors')
        selection={}
        with gzip.open(repo/plan['sourceGeometry'],'rb') as stream:
            for line in stream:
                row=json.loads(line);selection[row['sourceWay']]=row['baseEligible']
        require(len(selection)==52743,'Complete excluded major-way selection')
        cached=json.loads(gzip.decompress((repo/plan['cachedWays']).read_bytes()))
        known_closed={row['sourceWay'] for row in cached['knownWays'] if row['finalFallbackClosed']}
        require(len(known_closed)==367 and known_closed<=closed,'Complete cached closed-way subset')
        categories={kind:{'uniqueClosedWays':len(ways),'baseEligibleMajorWays':sum(selection.get(w) is True for w in ways),'baseIneligibleMajorWays':sum(selection.get(w) is False for w in ways),'outsideSelectedMajorTable':sum(w not in selection for w in ways),'cachedClosedWays':len(ways&known_closed)} for kind,ways in by_kind.items()}
        evidence={'allClosedWayContributorIds':dict(by_way),'closingRelations':details}
        raw=(json.dumps(evidence,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();require(len(raw)<=33554432,'Complete closure evidence cap')
        packed=gzip.compress(raw,mtime=0)
        with (root/'closure-evidence.json.gz').open('xb') as stream:stream.write(packed)
        save('report.json',{'status':'all_final_fallback_way_closure_contributors_reconstructed','recipeSha256':args.pin,
             'allRawUnsupportedRelations':count,'allCurrentSingleDecisions':len(single),'allCurrentMultiDecisions':len(multi),
             'allFinalClosedWaysAttributed':len(closed),'closingRelationCountsByKind':dict(relation_counts),
             'closedWayExposureByKind':categories,'uniqueWayCategoriesCanOverlap':True,'cachedClosedWays':len(known_closed),
             'artifact':{'file':'closure-evidence.json.gz','bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest(),'rawBytes':len(raw),'rawSha256':hashlib.sha256(raw).hexdigest()},
             'hostSecondsIncludingBindingsCompleteSourceRelationsDecisionsAndUnionReplay':time.monotonic()-began,'hostMaximumRssBytes':check(),
             'sourcePbfReads':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,'sourcePermissionsOrPricesChanged':False,'appActivated':False,
             'scope':'Every70376originalunsupportedcarrelation/current single+multi decision classified under unchanged source producer semantics; complete29657finalwayclosure union reconstructed and every independent contributor retained. Counts by category overlap for multiply contributed ways. All52743excluded major-way identities and367cached closed ways join only for scope/exposure; no road/corridor identity, causal routing improvement, permission or new model claim. Conditional category reflects current parser guard, not an evaluated condition. No source/graph/query/provider/app operation. Host512MiBRSS/300s/output64MiB; entire active candidate reservation retained under72GiBaggregate, not cgroup/cloud evidence.'})
    except BaseException as error:
        save('failure.json',{'status':'closure_inventory_stopped','error':repr(error)});raise


if __name__=='__main__':main()
