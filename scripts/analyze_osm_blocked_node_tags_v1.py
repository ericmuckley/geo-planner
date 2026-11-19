"""Inventory every original blocker tag and join all saved optimistic trials; no policy change."""
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_car_conditional_scope_v1 import node_policy,scoped_tags
from coarse_timing_input import require
from import_roads import CAR_KEYS,access_allowed

REPO=Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def exposures(evidence):
    tags=evidence['rawTags'];scoped=scoped_tags(tags)
    decision=node_policy(tags)
    require(evidence['rawBaseDecision']==decision,'Recorded raw base decision independently matches')
    key=next((key for key in CAR_KEYS if key in scoped),None)
    barrier=decision['barrier']
    return {'barrier':tags.get('barrier'),
            'barrierReason':barrier['reason'] if barrier else None,
            'effectiveAccessKey':key,'effectiveAccessValue':scoped.get(key) if key else None,
            'accessAllowed':access_allowed(scoped),
            'retainedConditionalKeys':sorted(key for key in scoped if key.endswith(':conditional')),
            'ignoredConditionalKeys':sorted(set(tags)-set(scoped)),
            'baseBlocked':decision['blocked'],
            'restrictionContributorCount':len(evidence['restrictionContributorIds']),
            'cause':evidence['cause']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('pin');args=parser.parse_args()
    began=time.monotonic();path=REPO/args.plan
    require(sha(path)==args.pin,'Blocker tags analysis recipe binding')
    plan=json.loads(path.read_bytes())
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']<72*1024**3,'Blocker analysis allocation')
    for name,pin in plan['bindings'].items():require(sha(REPO/name)==pin,'Blocker tags input: '+name)
    source=REPO/plan['tagEvidence'];before=source.stat();artifact=plan['tagArtifact']
    require(before.st_size==artifact['bytes'] and sha(source)==artifact['sha256'],'Complete tag evidence binding')
    with gzip.open(source,'rb') as stream:raw=stream.read(16777217)
    require(len(raw)==artifact['rawBytes']<=16777216 and hashlib.sha256(raw).hexdigest()==artifact['rawSha256'],'Complete raw tag evidence binding')
    original=json.loads(raw);evidence=original['nodeEvidence']
    require(len(evidence)==original['selectedNodes']==13776 and not original['unknownRawNodeIds'],'Every blocker raw tag known')
    require(source.stat()==before,'Complete tag evidence stat stable')
    old=json.loads((REPO/plan['priorCauseReport']).read_bytes())
    trial_ids=set();cases=[]
    counts={key:Counter() for key in ('cause','barrier','barrierReason','effectiveAccess','retainedConditionalKey')}
    by_barrier=defaultdict(Counter)
    for identity,row in evidence.items():
        require(time.monotonic()-began<300 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<=536870912,'Blocker tags analysis host deadline/RSS')
        require(str(row['sourceNodeId'])==identity and row['sourceBlockingReconciled'] and row['sourceSignalReconciled'],'Every source cause/identity reconciled')
        found=exposures(row)
        for key in ('cause','barrier','barrierReason'):counts[key][str(found[key])]+=1
        counts['effectiveAccess'][str(found['effectiveAccessKey'])+'='+str(found['effectiveAccessValue'])]+=1
        counts['retainedConditionalKey'].update(found['retainedConditionalKeys'])
        by_barrier[str(found['barrier'])][found['cause']]+=1
    for row in old['all83TrialAttachmentsRetained']:
        nodes=row['crossedBlockedNativeNodeIds'];trial_ids.update(nodes)
        cases.append({'id':row['id'],'optimisticRoadLegSavingsTicks':row['optimisticRoadLegSavingsTicks'],
                      'crossedBlockedNodes':[{'sourceNodeId':identity,'rawTags':evidence[identity]['rawTags'],
                                             'restrictionContributorIds':evidence[identity]['restrictionContributorIds'],
                                             **exposures(evidence[identity])} for identity in nodes]})
    require(len(cases)==83 and len(trial_ids)==32,'All saved trial cases/unique blockers retained')
    report={'status':'all_13776_original_blocker_tags_and_83_trials_inventoried','recipeSha256':args.pin,
            'blockedGraphNodes':len(evidence),'uniqueTrialBlockedNodes':len(trial_ids),'unknownRawNodes':0,
            'allNodeCauseCounts':original['causeCounts'],
            'tagExposureCounts':{key:dict(sorted(value.items())) for key,value in counts.items()},
            'barrierCauseCounts':{key:dict(value) for key,value in sorted(by_barrier.items())},
            'all83TrialCases':cases,
            'trialNodeExposureCounts':dict(Counter(exposures(evidence[key])['barrier'] or 'None' for key in trial_ids)),
            'routingQueries':0,'sourcePbfReads':0,'providerRequests':0,'applicationDbReads':0,
            'sourcePermissionsOrPricesChanged':False,'appActivated':False,
            'hostSecondsIncludingBindingsAllTagsAndTrialJoin':time.monotonic()-began,
            'hostMaximumRssBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
            'scope':'ALL13776 original graph blocker tags, all independent source causes, all83 saved optimistic fixed-attachment trials. Tag/reason histograms are observations, not a new access policy. Omitting blocks never establishes lawful passage or new point/map/model scores. Every independent node-only restriction contributor stays explicit; no route/place exceptions, tuning, queries or source changes.'}
    encoded=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode();require(len(encoded)<=2097152,'Blocker tag inventory output cap')
    with (REPO/plan['output']).open('xb') as stream:stream.write(encoded)
    print(json.dumps({key:report[key] for key in ('status','allNodeCauseCounts','trialNodeExposureCounts','hostSecondsIncludingBindingsAllTagsAndTrialJoin')}))


if __name__=='__main__':main()
