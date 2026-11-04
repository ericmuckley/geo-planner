"""Closed geometric-opportunity proof; no worker/PBF/fine/provider access.

--local-assets additionally checks every saved Census midpoint/weight against
its original bound spans. It does not establish physical road identity.
"""
import argparse
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2]
load=lambda p:json.loads(p.read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
KINDS=('allGeometry','anySpeedTag','plainNumeric','unscopedNumeric')
FALSE=('sourceAdequacyQualified','carPermissionReviewed','uniqueMatchesQualified','usableLimitOrMatchingQualified','modelChanged')


def summary(rows):
    km=math.fsum(r['sourceKm'] for r in rows)
    return {'arcWindowRecords':len(rows),'sourceKm':km,'samples':sum(r['sampleCount'] for r in rows),
            'unions':{name:{'alignedKm':math.fsum(r['unions'][name]['alignedKm'] for r in rows),'wholeArcOpportunityKm':math.fsum(r['unions'][name]['wholeArcOpportunityKm'] for r in rows),
                           'alignedFraction':math.fsum(r['unions'][name]['alignedKm'] for r in rows)/km if km else None,
                           'wholeArcOpportunityFraction':math.fsum(r['unions'][name]['wholeArcOpportunityKm'] for r in rows)/km if km else None} for name in KINDS}}


def span_length(a,b):
    lat1,lat2=map(math.radians,(a[1],b[1]));h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(b[0]-a[0])/2)**2
    return 12742*math.asin(min(1,math.sqrt(h)))


def verify(stage,local=False):
    from run_osm_speed_opportunity_v1 import validate,isolation
    plan=load(folder/f'speed-opportunity-plan-{stage}-v1.json');validate(plan);freeze=load(folder/f'speed-opportunity-freeze-{stage}-v1.json')
    assert sha(folder/f'speed-opportunity-plan-{stage}-v1.json')==freeze['recipeSha256']
    for path,pin in plan['inputs'].items():
        if not path.startswith('data/'):assert sha(repo/path)==pin
    for path,pin in freeze['newProducerFiles'].items():assert sha(repo/path)==pin
    closed=load(folder/f'speed-opportunity-closed-{stage}-v1.json');raw=folder/f'speed-opportunity-raw/{stage}-v1'
    assert closed['files']==len(closed['roster']) and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values()) and closed['usage']['logicalBytes']<=4194304
    for name,row in closed['roster'].items():assert not row['ignoredLargeAsset'] and (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
    assert closed['closerSha256']==sha(repo/'scripts/close_osm_speed_opportunity_v1.py')
    isolation(load(raw/'container-initial.json'));state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
    assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent'] and load(folder/f'speed-opportunity-cleanup-{stage}-v1.json')['independentlyAbsent']
    metrics=load(raw/'metrics.json');assert metrics['memory.max']=='536870912' and metrics['memory.swap.max']=='0' and int(metrics['memory.peak'])<=536870912 and 'oom 0' in metrics['memory.events'] and 'oom_kill 0' in metrics['memory.events']
    result=load(raw/'result.json');profile=load(raw/'opportunity.json');assert result['status']=='passed_geometry_opportunity_diagnostic'
    for key,name in [('opportunitySha256','opportunity.json'),('arcsSha256','arcs.jsonl'),('sampleMasksSha256','sample-masks.bin')]:assert result[key]==sha(raw/name)
    masks=(raw/'sample-masks.bin').read_bytes();arcs=[json.loads(line) for line in (raw/'arcs.jsonl').read_bytes().splitlines()]
    assert result['records']==profile['rows'] and profile['sampleMasksSha256']==result['sampleMasksSha256']
    assert profile['allWindows']['samples']==len(masks) and all(m in (0,1,3,7,15) for m in masks)
    assert len({(r['windowId'],r['arc']) for r in arcs})==len(arcs) and not any(profile[k] for k in FALSE)
    assert profile['allWindows']==summary(arcs)
    for key,stats in profile['classes'].items():assert stats==summary([r for r in arcs if r['sourceClassKph']==int(key)])
    assert [w['id'] for w in profile['windows']]==[w['id'] for w in plan['windows']]
    for window in profile['windows']:
        selected=[r for r in arcs if r['windowId']==window['id']];assert window['totals']==summary(selected)
        for key,stats in window['classes'].items():assert stats==summary([r for r in selected if r['sourceClassKph']==int(key)])
    for arc in arcs:
        assert arc['sourceKm']>0 and arc['sampleCount']>0
        previous=arc['sourceKm']
        for name in KINDS:
            metric=arc['unions'][name];assert 0<=metric['alignedKm']<=previous+1e-9;previous=metric['alignedKm']
            assert metric['fraction']==min(1.,metric['alignedKm']/arc['sourceKm'])
            assert metric['wholeArcOpportunityKm']==(arc['sourceKm'] if metric['fraction']>=.8-1e-12 else 0.)
    assert profile['comparisons']<=plan['dataCaps']['comparisons'] and profile['binVisits']<=plan['dataCaps']['binVisits']
    run=load(raw/'run-summary.json');assert run['exitCode']==run['networkRequests']==run['pbfOrNativeHelperReads']==0 and run['seconds']<=360 and result['seconds']<=300
    if stage=='controls':
        assert load(raw/'controls.json')=={'tests':10,'successful':True,'failures':0,'errors':0,'skips':0}
        assert len(arcs)==2 and len(masks)==22 and set(masks)=={7}
        assert profile['allWindows']['sourceKm']==10 and profile['allWindows']['unions']['plainNumeric']['alignedKm']==10 and profile['allWindows']['unions']['unscopedNumeric']['alignedKm']==0
    else:
        capture=load(folder/'disk-capture-plan-run-v1.json');assert plan['windows']==capture['windows']
        assert profile['rows']==profile['memberships']==1368072 and profile['types']=={'node':1123919,'relation':4900,'way':239253} and len(arcs)==2469
        assert profile['inputBytes']==477852579 and profile['inputSha256']=='efc36dc058b198711cc2666a751c9fd60b52d37902efbb22e1cba8b5f30f91f4'
        inventory=load(folder/'attribute-inventory-raw/run-v1/inventory.json');counts=profile['rawWayCategoryMaskCounts']
        assert sum(counts.values())==239253 and sum(v for k,v in counts.items() if int(k)&4)==inventory['allCapturedHighways']['plainNumericWays'] and sum(v for k,v in counts.items() if int(k)&8)==inventory['allCapturedHighways']['unscopedNumericWays']
        old=load(repo/'docs/evidence/coarse-timing-cache-2026-10-25/report.json')
        for window in profile['windows']:
            saved=next(w for w in old['windows'] if w['id']==window['id'])
            for k,stats in window['classes'].items():assert stats['arcWindowRecords']==saved['sourceClassesKph'][k]['arcCount'] and math.isclose(stats['sourceKm'],saved['sourceClassesKph'][k]['sourceKm'],abs_tol=1e-9)
        if local:
            path=repo/'data/coarse-quality/overture-timing-cache-analysis-v2/matches.jsonl';assert sha(path)==plan['inputs'][str(path.relative_to(repo))]
            source=[json.loads(line) for line in path.read_bytes().splitlines()];assert len(source)==len(arcs);position=0
            for saved,arc in zip(source,arcs):
                assert all(saved[k]==arc[k] for k in ('windowId','arc','sourceClassKph','sourceKm'))
                weights=[]
                for a,b,km in saved['sourceSpans']:
                    count=max(1,math.ceil(span_length(a,b)/.025));weights.extend([km/count]*count)
                assert len(weights)==arc['sampleCount']
                group=masks[position:position+len(weights)];position+=len(weights)
                for bit,name in enumerate(KINDS):assert math.isclose(arc['unions'][name]['alignedKm'],min(arc['sourceKm'],math.fsum(w for w,m in zip(weights,group) if m&(1<<bit))),abs_tol=1e-9)
            assert position==len(masks)
    return {'stage':stage,'linuxControls':10,'arcWindowRecords':len(arcs),'midpoints':len(masks),'allWeightedDenominatorsVerified':True,'originalLocalSpansAudited':stage=='run' and local,'workerAbsent':True,'usableLimitOrMatchingQualified':False,'modelChanged':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=['controls','run'],default='controls');parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
    saved=sys.argv
    try:
        sys.argv=[str(folder/'verify_attribute_inventory_run_v2.py')]
        with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
    finally:sys.argv=saved
    sys.path.insert(0,str(repo/'scripts'))
    if args.stage=='run':verify('controls')
    print(json.dumps(verify(args.stage,args.local_assets),indent=2))
