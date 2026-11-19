"""All cached source relations: metadata feasibility only, no source port/graph admission."""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_conditional_node_inventory_v1 import closure_unions
from coarse_osm_conditional_node_turns_v2 import POLICY,classify
from coarse_osm_country_screen_v1 import owned_usage
from coarse_timing_input import require

REPO=Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('pin');args=parser.parse_args()
    began=time.monotonic();recipe=REPO/args.plan;require(sha(recipe)==args.pin,'Conditional node inventory recipe binding');plan=json.loads(recipe.read_bytes())
    require(plan['output']=='data/coarse-quality/us-osm-conditional-node-turns-inventory-v1' and plan['policy']==POLICY,'Conditional node exact namespace/policy')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864<72*1024**3,'Conditional node inventory aggregate reserve')
    for name,pin in plan['bindings'].items():require(not name.endswith(('.pbf','/001.bin')) and sha(REPO/name)==pin,'Conditional node readonly binding: '+name)
    root=REPO/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def check():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        require(time.monotonic()-began<300 and rss<536870912 and owned_usage(root)['conservativeAllocatedBytes']<67108864,'Conditional node host deadline/RSS/owned cap')
        return rss
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=1048576,'Conditional node small record cap')
        with (root/name).open('xb') as stream:stream.write(raw)
    try:
        reasons=Counter();counts=Counter();candidates=[];previous=seen=0;digest=hashlib.sha256()
        with (REPO/plan['rawRelations']).open('rb') as stream:
            while line:=stream.readline(2097153):
                if seen%256==0:check()
                require(len(line)<=2097152 and line.endswith(b'\n') and seen<70376,'Complete bounded source relation corpus')
                digest.update(line);element=json.loads(line);require(previous<element['id'],'Source relation order');previous=element['id'];seen+=1
                result=classify(element);reasons[result['reason']]+=1
                if result['rule'] is not None:
                    rule=asdict(result['rule']);counts[rule['kind']]+=1
                    candidates.append({'source':element,'derived':{key:(str(value) if type(value) is int else value) for key,value in rule.items()}})
        require(seen==70376 and digest.hexdigest()==plan['bindings'][plan['rawRelations']],'Complete original source count/hash')
        with gzip.open(REPO/plan['closureEvidence'],'rb') as stream:raw=stream.read(33554433)
        require(len(raw)==plan['closureRawBytes']<=33554432 and hashlib.sha256(raw).hexdigest()==plan['closureRawSha256'],'Complete independently audited closure evidence')
        closure=json.loads(raw);converted={int(row['derived']['identity']) for row in candidates}
        original,potential_remaining=closure_unions(closure['closingRelations'],converted)
        require(len(original)==29657 and original=={int(key) for key in closure['allClosedWayContributorIds']},'Original whole closure union independently reproduces')
        potential_open=original-potential_remaining
        selected={};digest=hashlib.sha256();raw_bytes=0
        with gzip.open(REPO/plan['sourceGeometry'],'rb') as stream:
            while line:=stream.readline(4194305):
                require(len(line)<=4194304 and line.endswith(b'\n'),'Complete selected geometry bound')
                digest.update(line);raw_bytes+=len(line);row=json.loads(line);selected[row['sourceWay']]=row['baseEligible']
        require(len(selected)==52743 and raw_bytes==plan['geometryRawBytes'] and digest.hexdigest()==plan['geometryRawSha256'],'Complete source-way selection seal')
        evidence={'candidates':candidates,'potentialUnclosedWayIdsBeforeSourcePortValidation':[str(v) for v in sorted(potential_open)]}
        raw=(json.dumps(evidence,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();require(len(raw)<=16777216,'Complete conditional candidate evidence cap')
        packed=gzip.compress(raw,mtime=0)
        with (root/'candidate-metadata.json.gz').open('xb') as stream:stream.write(packed)
        # Reopen and independently classify every retained original after release of the source stream.
        restored=json.loads(gzip.decompress((root/'candidate-metadata.json.gz').read_bytes()))
        require(restored==evidence,'All original and derived metadata bytes roundtrip')
        for index,row in enumerate(restored['candidates']):
            if index%256==0:check()
            rule=asdict(classify(row['source'])['rule'])
            require({k:(str(v) if type(v) is int else v) for k,v in rule.items()}==row['derived'],'Every source conditional candidate replays after reopen')
        save('report.json',{'status':'all_cached_conditional_via_node_metadata_feasibility_audited','recipeSha256':args.pin,'policy':POLICY,
             'allRawUnsupportedRelations':seen,'classificationCounts':dict(reasons),'metadataCandidates':len(candidates),'candidateKinds':dict(counts),
             'allOriginalWayClosuresIndependentlyReconstructed':len(original),
             'potentialUnclosedWaysBeforeSourcePortValidation':len(potential_open),
             'potentialBaseEligibleMajorWaysBeforeSourcePortValidation':sum(selected.get(w) is True for w in potential_open),
             'potentialBaseIneligibleMajorWaysBeforeSourcePortValidation':sum(selected.get(w) is False for w in potential_open),
             'potentialOutsideMajorTableBeforeSourcePortValidation':sum(w not in selected for w in potential_open),
             'everyIndependentUnconvertedContributorRetained':True,'physicalSourcePortsValidated':False,
             'artifact':{'file':'candidate-metadata.json.gz','bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest(),'rawBytes':len(raw),'rawSha256':hashlib.sha256(raw).hexdigest()},
             'hostSecondsIncludingBindingsAllClassificationsClosureUnionsAndIndependentReplay':time.monotonic()-began,'hostMaximumRssBytes':check(),
             'sourcePbfReads':0,'sourceConstructorExecutions':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
             'sourcePermissionsOrPricesChanged':False,'appActivated':False,
             'scope':'All70376cached raw unsupported relations classified under one predeclared conservative single-kind via-node envelope. All29657original way closures independently rebuild and all unconverted contributors stay. Potential unclosed counts are metadata-only upper bounds; complete pre-closure directed incidences and via-node source support must validate before any closure removal, derived turn fact or graph operation. Every retained original tag/member/uint64 identity replays after output reopen. No condition evaluation, time selection, fit, query, model or app admission. Host512MiBRSS/300s/64MiBowned under72GiBaggregate, not cgroup/cloud evidence.'})
    except BaseException as error:
        save('failure.json',{'status':'conditional_node_inventory_stopped','error':repr(error)});raise


if __name__=='__main__':main()
