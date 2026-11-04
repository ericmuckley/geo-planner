"""Closed native matcher proof and optional independent binding/weight audit.

Local mode reads the new derived matcher files, original small Census spans and
sealed audit SQLite, never source PBF/fine/native/provider or application DB.
"""
import argparse
from collections import Counter,defaultdict
import contextlib
from functools import lru_cache
import hashlib
import io
import json
import math
from pathlib import Path
import runpy
import sqlite3
import sys
import time

folder=Path(__file__).resolve().parent;repo=folder.parents[2]
load=lambda p:json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
FALSE=('sourceAdequacyQualified','carPermissionReviewed','uniquePhysicalMatchQualified','usableLimitOrMatchingQualified','modelChanged')
ROLES=set('motorway trunk primary secondary tertiary residential living_street unclassified service motorway_link trunk_link primary_link secondary_link tertiary_link'.split())


def totals(records):
    km=math.fsum(r['sourceKm'] for r in records);single=[r for r in records if r['status']=='single_acquired_file_geometric_path']
    potential=math.fsum(r['candidates'][0]['maximumSupportedKm'] for r in single if r['candidates'][0]['allUnscopedNumeric'])
    return {'arcWindowRecords':len(records),'sourceKm':km,'samples':sum(r['sampleCount'] for r in records),'statusCounts':dict(Counter(r['status'] for r in records)),
            'statusSourceKm':{s:math.fsum(r['sourceKm'] for r in records if r['status']==s) for s in sorted({r['status'] for r in records})},'singleGeometricPathRecords':len(single),
            'singlePathUnscopedNumericSupportedKm':potential,'singlePathUnscopedNumericFraction':potential/km if km else None,
            'cappedRecords':sum(r['searchCapped'] for r in records),'usableLimitOrMatchingQualified':False,'modelChanged':False}


def equivalent(a,b):
    if isinstance(b,dict):
        assert set(a)==set(b)
        for k in b:equivalent(a[k],b[k])
    elif isinstance(b,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):equivalent(x,y)
    elif type(b) is float:assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(a,b)
    else:assert a==b,(a,b)


def distance(a,b):
    x,y=map(math.radians,(a[1],b[1]));h=math.sin((y-x)/2)**2+math.cos(x)*math.cos(y)*math.sin(math.radians(b[0]-a[0])/2)**2
    return 12742*math.atan2(math.sqrt(min(1,h)),math.sqrt(max(0,1-h)))


def local_audit(plan,closed,profile):
    from coarse_osm_attributes_v1 import numeric_speed
    began=time.monotonic();root=repo/closed['root'];source_path=repo/'data/coarse-quality/overture-timing-cache-analysis-v2/matches.jsonl'
    assert sha(source_path)==plan['inputs'][str(source_path.relative_to(repo))]
    original=[json.loads(line) for line in source_path.read_bytes().splitlines()];source={(r['windowId'],r['arc']):r for r in original};assert len(source)==2469
    captured=load(folder/'disk-capture-closed-run-v1.json');db_path=repo/captured['root']/'extract/audit-selected.sqlite';before=db_path.stat();pin=captured['roster']['extract/audit-selected.sqlite'];assert before.st_size==pin['bytes'] and sha(db_path)==pin['sha256']
    db=sqlite3.connect(db_path.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');assert db.execute('PRAGMA quick_check').fetchone()==('ok',)
    windows=[w['id'] for w in plan['windows']];snapshot=plan['sourceSnapshotUtc'];all_records=[];reviews=[];binding_count=variants=0;reason_counts=Counter();reason_arc_km=defaultdict(float);short_parts=all_unrepresented=0;issue_arc_counts=Counter();part_length_bins=Counter();all_reason_sets=Counter()
    @lru_cache(maxsize=65536)
    def node(identity):
        row=db.execute("SELECT raw FROM objects WHERE kind='node' AND id=?",(identity,)).fetchone();assert row is not None
        return row[0],json.loads(row[0])
    def read(name):
        path=root/name;assert path.stat().st_size==closed['roster'][name]['bytes'] and sha(path)==closed['roster'][name]['sha256'];return path
    try:
        for wi,window in enumerate(plan['windows']):
            wid=window['id'];bindings={r['ordinal']:r for r in (json.loads(line) for line in read('windows/'+wid+'/part-bindings.jsonl').read_bytes().splitlines())} if 'windows/'+wid+'/part-bindings.jsonl' in closed['roster'] else {}
            query="SELECT o.id,o.raw FROM objects o JOIN memberships m ON o.kind=m.kind AND o.id=m.id WHERE o.kind='way' AND m.w=? ORDER BY o.id"
            counts=Counter();way_count=refs_count=0
            for _,raw in db.execute(query,(wi,)):
                e=json.loads(raw);counts.update(e['nodes']);way_count+=1;refs_count+=len(e['nodes'])
            ordinal=0;role_counts=Counter();lengths={};checked_bindings=set();parent_seals={}
            for identity,raw in db.execute(query,(wi,)):
                e=json.loads(raw);refs=e['nodes'];tags=e['tags'];cuts=[0,*[i for i in range(1,len(refs)-1) if counts[refs[i]]>1],len(refs)-1]
                for first,last in zip(cuts,cuts[1:]):
                    role_counts[tags.get('highway','')]+=1
                    if ordinal in bindings:
                        binding=bindings[ordinal];checked_bindings.add(ordinal);line=[[node(n)[1]['lon'],node(n)[1]['lat']] for n in refs[first:last+1]];lengths[ordinal]=math.fsum(distance(a,b) for a,b in zip(line,line[1:]))
                        if identity not in parent_seals:
                            geometry=hashlib.sha256(b'['+canonical(snapshot)+b',[')
                            for i,n in enumerate(refs):
                                if i:geometry.update(b',')
                                geometry.update(node(n)[0])
                            geometry.update(b']]');geometry_hash=geometry.hexdigest();members=[windows[i] for i, in db.execute("SELECT w FROM memberships WHERE kind='way' AND id=? ORDER BY w",(identity,))]
                            full={'publisherStateUtc':snapshot,'element':e,'elementSha256':hashlib.sha256(raw).hexdigest(),'geometryDependencySha256':geometry_hash,'windowIds':members}
                            parent_seals[identity]=(full['elementSha256'],geometry_hash,hashlib.sha256(canonical(full)+b'\n').hexdigest())
                        field_pin,geometry_pin,line_pin=parent_seals[identity]
                        expected_reasons=[]
                        if tags.get('highway') not in ROLES:expected_reasons.append('unsupported_native_road_role')
                        if refs[first]==refs[last]:expected_reasons.append('same_native_endpoint_identity')
                        if not any(a!=b for a,b in zip(line,line[1:])):expected_reasons.append('degenerate_native_geometry')
                        def family(names):return {k:v for k,v in tags.items() if any(k==name or k.startswith(name+':') for name in names)}
                        speed=numeric_speed(tags.get('maxspeed'));scopes={k:v for k,v in tags.items() if k.startswith('maxspeed:') and k not in {'maxspeed:type','maxspeed:reason'}}
                        attrs={'speed':speed,'speedScopeTags':scopes,'unscopedNumeric':speed['status']=='plain_numeric' and not scopes,'accessTags':family(('access','vehicle','motor_vehicle','motorcar')),'directionTags':family(('oneway',)),
                               'structureTags':family(('bridge','tunnel','layer','level','location','junction','construction','proposed')),'carPermission':'unreviewed','usableForTiming':False,
                               'barrierNodeIds':[n for n in refs[first:last+1] if 'barrier' in node(n)[1]['tags']]}
                        expected={'ordinal':ordinal,'nativeWayId':identity,'nativeWayVersion':e['version'],'firstNodeIndex':first,'lastNodeIndex':last,'elementSha256':field_pin,'geometryDependencySha256':geometry_pin,'rawLineSha256':line_pin,
                                  'endpointIds':[refs[first],refs[last]],'endpoints':[line[0],line[-1]],'baseReasons':expected_reasons,'nativeTags':tags,'attributes':attrs}
                        equivalent(binding,expected);binding_count+=1
                    ordinal+=1
            assert checked_bindings==set(bindings)
            report=load(read('windows/'+wid+'/report.json'));scan=report['captureScan'];assert scan['ways']==way_count and scan['references']==refs_count and scan['parts']==ordinal and scan['sharedNativeNodes']==sum(n>1 for n in counts.values()) and report['nativePartRoleCounts']==dict(role_counts) and report['alignedPartBindings']==len(bindings)
            records=[json.loads(line) for line in read('windows/'+wid+'/matches.jsonl').read_bytes().splitlines()];assert len(records)==report['totals']['arcWindowRecords'];assert len({r['arc'] for r in records})==len(records)
            for r in records:
                saved=source[r['windowId'],r['arc']];assert r['sourceClassKph']==saved['sourceClassKph'] and math.isclose(r['sourceKm'],saved['sourceKm'],abs_tol=1e-9) and r['sourceRecordSha256']==hashlib.sha256(canonical(saved)).hexdigest()
                weights=[]
                for a,b,km in saved['sourceSpans']:
                    n=max(1,math.ceil(distance(a,b)/.025));weights.extend([km/n]*n)
                assert len(weights)==r['sampleCount'] and math.isclose(math.fsum(weights),r['sourceKm'],abs_tol=1e-9) and not any(r[k] for k in FALSE)
                issue_by_part={i['ordinal']:i for i in r.get('fragmentIssues',[])};reasons=set()
                for part in r['unrepresentedParts']:
                    assert part in bindings;issue=issue_by_part.get(part,{});codes=issue.get('reasons',[]) or ['no_eligible_fragment_variant']
                    reason_counts.update(codes);reasons.update(codes);all_unrepresented+=1
                    length=lengths[part];short_parts+=int(length<=.025);part_length_bins['<=25m' if length<=.025 else '<=50m' if length<=.05 else '<=100m' if length<=.1 else '>100m']+=1
                for reason in reasons:reason_arc_km[reason]+=r['sourceKm'];issue_arc_counts[reason]+=1
                if reasons:all_reason_sets['|'.join(sorted(reasons))]+=1
                for candidate in r['candidates']:
                    key=candidate['nativeParts'];assert key and all(i in bindings for i in key) and tuple(key)==min(tuple(key),tuple(reversed(key)))
                    assert candidate['allUnscopedNumeric']==all(bindings[i]['attributes']['unscopedNumeric'] for i in key)
                    supported=[]
                    for variant in candidate['variants']:
                        variants+=1;path=variant['rowOrdinals'];assert path==key or path==list(reversed(key));assert len(path)==len(variant['variantKeys'])
                        mask=int(variant['coveredSampleMaskHex'],16);assert mask>=0 and mask.bit_length()<=len(weights);km=math.fsum(w for i,w in enumerate(weights) if mask>>i&1);assert math.isclose(km,variant['supportedKm'],abs_tol=1e-9) and variant['fraction']>=.8-1e-12 and math.isclose(variant['fraction'],min(1,km/r['sourceKm']),abs_tol=1e-10)
                        for a,b in zip(path,path[1:]):assert set(bindings[a]['endpointIds'])&set(bindings[b]['endpointIds'])
                        supported.append(km)
                    assert supported and math.isclose(candidate['maximumSupportedKm'],max(supported),abs_tol=1e-9)
                if r['status']=='single_acquired_file_geometric_path':
                    assert len(r['candidates'])==1 and not r['unrepresentedParts'] and not r['searchCapped']
                    identity=[(bindings[i]['nativeWayId'],bindings[i]['nativeWayVersion'],bindings[i]['firstNodeIndex'],bindings[i]['lastNodeIndex']) for i in r['candidates'][0]['nativeParts']]
                    rank=hashlib.sha256(canonical([snapshot,identity,wid])).hexdigest();reviews.append({'rank':rank,'windowId':wid,'arc':r['arc'],'nativePathIdentity':[list(v) for v in identity],'sourceRecordSha256':r['sourceRecordSha256'],'physicalMatchReviewed':False,'usableForTiming':False})
            equivalent(report['totals'],totals(records))
            for k,v in report['classes'].items():equivalent(v,totals([r for r in records if r['sourceClassKph']==int(k)]))
            all_records.extend(records);assert time.monotonic()-began<1800
        assert len(all_records)==2469 and {(r['windowId'],r['arc']) for r in all_records}==set(source)
        equivalent(profile['allWindows'],totals(all_records))
        for k,v in profile['classes'].items():equivalent(v,totals([r for r in all_records if r['sourceClassKph']==int(k)]))
        expected_review=sorted(reviews,key=lambda r:(r['rank'],r['arc']))[:50];assert load(read('review-selection.json'))['records']==expected_review
    finally:db.close()
    assert db_path.stat()==before
    return {'auditorSha256':sha(Path(__file__)),'closedRosterSha256':sha(folder/'native-match-closed-run-v1.json'),'reportSha256':sha(root/'report.json'),'completeSavedWeightBindingAndNativeLineageAudit':True,'sourceArcWindowRecords':2469,'midpoints':85629,'nativePartBindingsChecked':binding_count,'candidateVariantsChecked':variants,'deterministicReviewRecordsVerified':len(expected_review),
            'sealedAuditDatabaseSha256':pin['sha256'],'sourceKm':profile['allWindows']['sourceKm'],'unrepresentedPartOccurrences':all_unrepresented,'unrepresentedPartsAtMost25m':short_parts,'unrepresentedPartLengthBins':dict(part_length_bins),'unrepresentedReasonPartOccurrences':dict(reason_counts),'unrepresentedReasonArcCounts':dict(issue_arc_counts),'unrepresentedReasonArcKm':dict(reason_arc_km),'unrepresentedReasonSetsArcCounts':dict(all_reason_sets),
            'reasonWeightScope':'Each reason exposure counts an original arc once if present; exposures overlap. Part occurrences repeat across arcs. Lengths are full native part lengths, not Census weights. No filtering or changed matches.',
            'seconds':time.monotonic()-began,'networkRequests':0,'pbfOrFineReads':0,'appDatabaseReads':0,'modelChanged':False,'usableLimitOrMatchingQualified':False,
            'method':'All original source identities/weights/classes; independent SQLite-native node/way/shared-junction/part/raw/field/geometry/lineage reconstruction, every saved candidate mask/weight/node-ID join, every window/class summary and exact deterministic50review list. Shared qualified numeric unit parser; no independent physical road identity, permission, complete competitor geometric enumeration or source adequacy claim.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');parser.add_argument('--record',action='store_true');args=parser.parse_args();assert not args.record or args.local_assets
    saved=sys.argv
    try:
        sys.argv=[str(folder/'verify_native_match_controls_v1.py')]
        with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
    finally:sys.argv=saved
    from run_osm_native_match_v1 import validate,isolation
    plan=load(folder/'native-match-plan-run-v1.json');validate(plan);freeze=load(folder/'native-match-freeze-run-v1.json');assert sha(folder/'native-match-plan-run-v1.json')==freeze['recipeSha256']=='251fda35d24c5de9433584fe4132170ba9e06f5fd218250201d084e451259ca9'
    for path,pin in plan['inputs'].items():
        if not path.startswith('data/'):assert sha(repo/path)==pin
    for path,pin in freeze['newProducerFiles'].items():assert sha(repo/path)==pin
    closed=load(folder/'native-match-closed-run-v1.json');mirror=folder/'native-match-raw/run-v1';assert closed['files']==len(closed['roster'])==76 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==31043244 and closed['usage']['logicalBytes']<=536870912
    for name,row in closed['roster'].items():
        if not row['ignoredLargeAsset']:assert (mirror/name).stat().st_size==row['bytes'] and sha(mirror/name)==row['sha256']
    assert closed['closerSha256']==sha(repo/'scripts/close_osm_native_match_v1.py')
    isolation(load(mirror/'container-initial.json'));state=load(mirror/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
    assert load(mirror/'cleanup.json')['removed'] and load(mirror/'cleanup.json')['independentInspectAbsent'] and load(folder/'native-match-cleanup-run-v1.json')['independentlyAbsent']
    metrics=load(mirror/'metrics.json');assert metrics['memory.max']=='1073741824' and metrics['memory.swap.max']=='0' and 'oom 0' in metrics['memory.events'] and 'oom_kill 0' in metrics['memory.events']
    profile=load(mirror/'report.json');result=load(mirror/'result.json');assert result['status']=='passed_native_geometry_diagnostic' and result['reportSha256']==sha(mirror/'report.json') and result['reviewSha256']==sha(mirror/'review-selection.json') and not any(profile[k] for k in FALSE)
    assert plan['windows']==load(folder/'disk-capture-plan-run-v1.json')['windows'] and profile['allWindows']['arcWindowRecords']==2469 and profile['allWindows']['samples']==85629 and profile['allWindows']['cappedRecords']==0
    assert profile['captureReceipt']['sha256']=='efc36dc058b198711cc2666a751c9fd60b52d37902efbb22e1cba8b5f30f91f4' and profile['captureReceipt']['types']=={'node':1123919,'relation':4900,'way':239253}
    old=load(repo/'docs/evidence/coarse-timing-cache-2026-10-25/report.json')
    for window in profile['windows']:
        previous=next(w for w in old['windows'] if w['id']==window['id'])
        for k,v in window['classes'].items():assert v['arcWindowRecords']==previous['sourceClassesKph'][k]['arcCount'] and math.isclose(v['sourceKm'],previous['sourceClassesKph'][k]['sourceKm'],abs_tol=1e-9)
    run=load(mirror/'run-summary.json');assert run['exitCode']==run['networkRequests']==run['pbfOrNativeHelperReads']==0 and run['seconds']<=1860 and result['seconds']<=1800
    if args.local_assets:
        record=local_audit(plan,closed,profile)
        if args.record:
            with (folder/'native-match-independent-audit-v1.json').open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
    else:
        record=load(folder/'native-match-independent-audit-v1.json');assert record['auditorSha256']==sha(Path(__file__)) and record['closedRosterSha256']==sha(folder/'native-match-closed-run-v1.json') and record['reportSha256']==result['reportSha256'] and record['completeSavedWeightBindingAndNativeLineageAudit']
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
