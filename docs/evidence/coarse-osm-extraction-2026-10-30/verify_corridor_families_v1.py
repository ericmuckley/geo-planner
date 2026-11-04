"""Saved topology proof; optional independent disjoint-set audit of all cases."""
from collections import Counter,defaultdict
import argparse
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import sys
import time

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
ROLES=set('motorway trunk primary secondary tertiary residential living_street unclassified service motorway_link trunk_link primary_link secondary_link tertiary_link'.split())


def equivalent(a,b):
    if isinstance(b,dict):
        assert set(a)==set(b)
        for k in b:equivalent(a[k],b[k])
    elif isinstance(b,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):equivalent(x,y)
    elif type(b) is float:assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(a,b)
    else:assert a==b,(a,b)


def summary(records):
    km=math.fsum(r['sourceKm'] for r in records);opportunity=math.fsum(r['unbranchedUnscopedSupportedOpportunityKm'] for r in records)
    return {'arcWindowRecords':len(records),'sourceKm':km,'samples':sum(r['sampleCount'] for r in records),'familyStatusCounts':dict(Counter(r['familyStatus'] for r in records)),
            'familyStatusSourceKm':{s:math.fsum(r['sourceKm'] for r in records if r['familyStatus']==s) for s in sorted({r['familyStatus'] for r in records})},
            'unbranchedUnscopedSupportedOpportunityKm':opportunity,'unbranchedUnscopedSupportedOpportunityFraction':opportunity/km if km else None,'usableLimitOrMatchingQualified':False,'modelChanged':False}


def local_audit(closed,report):
    began=time.monotonic();root=repo/closed['root'];parent=load(folder/'continuous-match-closed-run-v2.json');native=repo/parent['root']
    source_path=repo/'data/coarse-quality/overture-timing-cache-analysis-v2/matches.jsonl';plan=load(folder/'corridor-family-plan-v1.json');assert sha(source_path)==plan['inputs'][str(source_path.relative_to(repo))]
    source={(r['windowId'],r['arc']):r for r in (json.loads(line) for line in source_path.read_bytes().splitlines())}
    own=root/'families.jsonl';assert sha(own)==closed['roster']['families.jsonl']['sha256'];saved={(r['windowId'],r['arc']):r for r in (json.loads(line) for line in own.read_bytes().splitlines())};assert set(saved)==set(source) and len(saved)==2469
    rows=[];components_checked=0
    for window in load(native/'report.json')['windows']:
        wid=window['id'];prefix='windows/'+wid+'/'
        for name in ('part-bindings.jsonl','matches.jsonl'):assert sha(native/prefix/name)==parent['roster'][prefix+name]['sha256']
        bindings={r['ordinal']:r for r in (json.loads(line) for line in (native/prefix/'part-bindings.jsonl').read_bytes().splitlines())};selected=[]
        with (native/prefix/'matches.jsonl').open('rb') as stream:
            for line in stream:
                assert len(line)<=67108864;r=json.loads(line);key=r['windowId'],r['arc'];out=saved[key];original=source[key];weights=[]
                for a,b,km in original['sourceSpans']:
                    x,y=map(math.radians,(a[1],b[1]));h=math.sin((y-x)/2)**2+math.cos(x)*math.cos(y)*math.sin(math.radians(b[0]-a[0])/2)**2;length=12742*math.asin(min(1,math.sqrt(h)));n=max(1,math.ceil(length/.025));weights.extend([km/n]*n)
                assert len(weights)==r['sampleCount'] and math.isclose(math.fsum(weights),r['sourceKm'],abs_tol=1e-9)
                parts={p for c in r['candidates'] for p in c['nativeParts']};union=0;variants=0;parents={};degrees=Counter()
                def find(n):
                    parents.setdefault(n,n)
                    while parents[n]!=n:parents[n]=parents[parents[n]];n=parents[n]
                    return n
                for p in parts:
                    a,b=bindings[p]['endpointIds'];degrees[a]+=1;degrees[b]+=1;ra,rb=find(a),find(b);parents[rb]=ra
                nodes_by_root=defaultdict(set);edges_by_root=Counter()
                for n in list(parents):nodes_by_root[find(n)].add(n)
                for p in parts:edges_by_root[find(bindings[p]['endpointIds'][0])]+=1
                comps=[{'nodes':len(nodes),'parts':edges_by_root[root],'branchNodes':sum(degrees[n]>2 for n in nodes),'cycle':edges_by_root[root]>=len(nodes)} for root,nodes in nodes_by_root.items()];components_checked+=len(comps)
                assert sorted((c['nodes'],c['parts'],c['branchNodes'],c['cycle']) for c in out['components'])==sorted((c['nodes'],c['parts'],c['branchNodes'],c['cycle']) for c in comps)
                for c in r['candidates']:
                    for v in c['variants']:union|=int(v['coveredSampleMaskHex'],16);variants+=1
                if r['searchCapped']:status='capped_original_search'
                elif not r['candidates']:status='no_saved_candidate'
                elif any(c['branchNodes'] or c['cycle'] for c in comps):status='branch_or_cycle_in_candidate_union'
                elif len(comps)>1:status='multiple_disconnected_corridors'
                else:status='one_unbranched_candidate_corridor'
                unscoped=bool(parts) and all(bindings[p]['attributes']['unscopedNumeric'] for p in parts);supported=bool(parts) and all(bindings[p]['nativeTags'].get('highway') in ROLES for p in parts);km=math.fsum(w for i,w in enumerate(weights) if union>>i&1)
                expected={k:r[k] for k in ('windowId','arc','sourceClassKph','sourceKm','sampleCount')}|{'originalStatus':r['status'],'familyStatus':status,'savedCandidatePaths':len(r['candidates']),'savedCandidateVariants':variants,'nativePartsInCandidateUnion':len(parts),'components':out['components'],'candidateUnionAlignedKm':km,'allUnscopedNumeric':unscoped,'allSupportedNativeRoles':supported,'unbranchedUnscopedSupportedOpportunityKm':km if status=='one_unbranched_candidate_corridor' and unscoped and supported else 0.,'rawAccessTagParts':sum(bool(bindings[p]['attributes']['accessTags']) for p in parts),'originalRejectedAlignedParts':len(r['unrepresentedParts']),'sourceAdequacyQualified':False,'physicalMatchQualified':False,'usableLimitOrMatchingQualified':False,'modelChanged':False}
                equivalent(out,expected);rows.append(out);selected.append(out)
        produced=load(root/'windows'/f'{wid}.json');equivalent(produced['totals'],summary(selected))
        for k,v in produced['classes'].items():equivalent(v,summary([r for r in selected if r['sourceClassKph']==int(k)]))
    assert len(rows)==2469;equivalent(report['allWindows'],summary(rows))
    for k,v in report['classes'].items():equivalent(v,summary([r for r in rows if r['sourceClassKph']==int(k)]))
    return {'auditorSha256':sha(Path(__file__)),'closedRosterSha256':sha(folder/'corridor-family-closed-v2.json'),'reportSha256':sha(root/'report.json'),'allOriginalCasesAndComponentsIndependentlyVerified':True,'sourceArcWindowRecords':2469,'weightedMidpoints':85629,'nativeCandidateComponentsChecked':components_checked,'independentMethod':'Disjoint-set components/counter degrees and independent source-mask weights, separate from producer DFS; all source identities/classes/areas preserved. No physical/source/car permission/usable timing proof.','seconds':time.monotonic()-began,'modelChanged':False,'usableLimitOrMatchingQualified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');parser.add_argument('--record',action='store_true');args=parser.parse_args();assert not args.record or args.local_assets
    saved=sys.argv
    try:
        sys.argv=[str(folder/'verify_continuous_match_run_v2.py')]
        with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
    finally:sys.argv=saved
    plan=load(folder/'corridor-family-plan-v1.json');freeze=load(folder/'corridor-family-freeze-v1.json');assert sha(folder/'corridor-family-plan-v1.json')==freeze['recipeSha256']=='d4b59ed2673695f1c386e036289e20b1ccccad80a780892bcf0a24936c11b59c'
    for path,pin in plan['inputs'].items():
        if not path.startswith('data/'):assert sha(repo/path)==pin
    for path,pin in freeze['newProducerFiles'].items():assert sha(repo/path)==pin
    stop=load(folder/'corridor-family-closure-stop-v1.json');assert stop['closerSha256']==sha(repo/'scripts/close_osm_corridor_families_v1.py')
    closed=load(folder/'corridor-family-closed-v2.json');raw=folder/'corridor-family-raw-v2';assert closed['files']==len(closed['roster'])==31 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==1777562
    for name,row in closed['roster'].items():
        if not row['ignoredLargeAsset']:assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
    assert closed['closerSha256']==sha(repo/'scripts/close_osm_corridor_families_v2.py') and load(folder/'corridor-family-cleanup-v2.json')['independentlyAbsent']
    assert load(raw/'controls.json')=={'tests':8,'successful':True,'skips':0}
    state=load(raw/'state.json');container=load(raw/'container-result.json');assert state['status']=='diagnostic_complete_source_incomplete' and container['State']['ExitCode']==0 and not container['State']['OOMKilled'] and container['Limits']=={'Memory':1073741824,'MemorySwap':1073741824,'ReadonlyRootfs':True,'NetworkMode':'none'}
    assert state['networkRequests']==state['routingQueries']==0 and not state['originalFeasibilityQualified'] and state['elapsedSeconds']<=360
    metrics=load(raw/'metrics.json');assert metrics['memory.max']=='1073741824' and metrics['memory.swap.max']=='0' and metrics['cpu.max']=='200000 100000' and metrics['tmpBytes']==67108864 and int(metrics['memory.peak'])<=1073741824 and 'oom 0' in metrics['memory.events'] and 'oom_kill 0' in metrics['memory.events']
    report=load(raw/'report.json');assert report['allWindows']['arcWindowRecords']==2469 and report['allWindows']['samples']==85629 and not any(report[k] for k in ('sourceAdequacyQualified','physicalMatchQualified','usableLimitOrMatchingQualified','modelChanged'))
    if args.local_assets:
        record=local_audit(closed,report)
        if args.record:
            with (folder/'corridor-family-independent-audit-v1.json').open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
    else:
        record=load(folder/'corridor-family-independent-audit-v1.json');assert record['auditorSha256']==sha(Path(__file__)) and record['closedRosterSha256']==sha(folder/'corridor-family-closed-v2.json') and record['reportSha256']==sha(raw/'report.json') and record['allOriginalCasesAndComponentsIndependentlyVerified']
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
