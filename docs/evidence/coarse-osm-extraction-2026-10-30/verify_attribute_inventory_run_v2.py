"""Verify closed inventory records; optional independent captured-JSONL statistics audit.

Never starts a worker, reads a PBF/fine index, or rewrites measured evidence.
"""
import argparse
from array import array
from bisect import bisect_left
from collections import Counter
import contextlib
from decimal import Decimal
import hashlib
import io
import json
import math
from pathlib import Path
import re
import runpy
import sys

folder=Path(__file__).resolve().parent
repo=folder.parents[2]
load=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ROLES=set('motorway trunk primary secondary tertiary residential living_street unclassified service motorway_link trunk_link primary_link secondary_link tertiary_link'.split())
ANNOTATIONS={'maxspeed:type','maxspeed:reason'}
COUNTS=('ways','plainNumericWays','unscopedNumericWays','speedScopeWays','accessTagWays','conditionalAccessWays','directionTagWays')
LENGTHS=('clippedMeters','plainNumericMeters','unscopedNumericMeters')
FALSE_FLAGS=('sourceOrPublisherAdequacyQualified','permissionsReviewed','usableForTiming','usableLimitOrMatchingGateQualified','modelChanged')


def stats_valid(s):
    assert all(type(s[k]) is int and 0<=s[k]<=s['ways'] for k in COUNTS)
    assert all(type(s[k]) in (int,float) and math.isfinite(s[k]) and s[k]>=0 for k in LENGTHS)
    assert 0<=s['unscopedNumericMeters']<=s['plainNumericMeters']<=s['clippedMeters']
    assert s['unscopedNumericWays']<=s['plainNumericWays']<=s['ways']
    for prefix in ('plainNumeric','unscopedNumeric'):
        expected=s[prefix+'Meters']/s['clippedMeters'] if s['clippedMeters'] else None
        assert s[prefix+'LengthFraction']==expected


def compare(actual,expected,path='inventory'):
    if isinstance(expected,dict):
        assert set(actual)==set(expected),path
        for k in expected:compare(actual[k],expected[k],path+'.'+k)
    elif isinstance(expected,list):
        assert len(actual)==len(expected),path
        for i,(a,b) in enumerate(zip(actual,expected)):compare(a,b,path+str(i))
    elif type(expected) is float:
        assert math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-5),(path,actual,expected)
    else:assert actual==expected,(path,actual,expected)


def clipped(a,b,box):
    # Independent slab intersection, rather than the producer's edge-clipping code.
    low,high=0.,1.
    for axis in range(2):
        delta=b[axis]-a[axis]
        if delta==0:
            if not box[axis]<=a[axis]<=box[axis+2]:return None
        else:
            t0=(box[axis]-a[axis])/delta;t1=(box[axis+2]-a[axis])/delta
            low=max(low,min(t0,t1));high=min(high,max(t0,t1))
            if low>high:return None
    return low,high


def metres(a,b,lo,hi):
    p=[a[i]+lo*(b[i]-a[i]) for i in (0,1)];q=[a[i]+hi*(b[i]-a[i]) for i in (0,1)]
    lat1,lat2=map(math.radians,(p[1],q[1]));dlat=lat2-lat1;dlon=math.radians(q[0]-p[0])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 12742000*math.atan2(math.sqrt(min(1,h)),math.sqrt(max(0,1-h)))


def empty():return dict.fromkeys(COUNTS,0)|dict.fromkeys(LENGTHS,0.)


def add(s,f,length):
    s['ways']+=1;s['clippedMeters']+=length
    for flag,prefix in ((f[0],'plainNumeric'),(f[1],'unscopedNumeric')):
        if flag:s[prefix+'Ways']+=1;s[prefix+'Meters']+=length
    for flag,key in zip(f[2:],COUNTS[3:]):s[key]+=int(flag)


def finish(s):
    return s|{prefix+'LengthFraction':s[prefix+'Meters']/s['clippedMeters'] if s['clippedMeters'] else None for prefix in ('plainNumeric','unscopedNumeric')}


def source_flags(tags):
    raw=tags.get('maxspeed');status='missing';unit='unknown'
    if raw is not None:
        match=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)(?: (mph|km/h))?',raw) if len(raw)<=256 else None
        status='unrecognized'
        if match:
            number=Decimal(match[1])*(Decimal('1.609344') if match[2]=='mph' else 1)
            if number>0 and math.isfinite(float(number)):status='plain_numeric';unit=match[2] or 'km/h'
            else:status='nonpositive_or_nonfinite'
    scoped=any(k.startswith('maxspeed:') and k not in ANNOTATIONS for k in tags)
    access=[k for k in tags if any(k==base or k.startswith(base+':') for base in ('access','vehicle','motor_vehicle','motorcar'))]
    return (status=='plain_numeric',status=='plain_numeric' and not scoped,scoped,bool(access),any(k.endswith(':conditional') for k in access),any(k=='oneway' or k.startswith('oneway:') for k in tags)),status,unit


def local_audit(plan,profile):
    path=repo/'data/coarse-quality/us-osm-disk-capture-run-v1/extract/elements.jsonl'
    before=path.stat();assert before.st_size==477852579
    ids=array('q');xs=array('i');ys=array('i');boxes={w['id']:w['bbox'] for w in plan['windows']}
    total=empty();supported=empty();roles={r:empty() for r in sorted(ROLES|{'other'})}
    windows={w:{'id':w,'types':Counter(),'allCapturedHighways':empty(),'supportedRoadRoles':empty()} for w in boxes}
    types=Counter();statuses=Counter();units=Counter();hashed=hashlib.sha256();rows=byte_count=occurrences=refs=raw_nodes=barriers=0
    with path.open('rb') as stream:
        for line in stream:
            assert len(line)<=8388608 and line.endswith(b'\n');rows+=1;byte_count+=len(line);hashed.update(line)
            record=json.loads(line);element=record['element'];kind=element['type'];members=record['windowIds'];types[kind]+=1;occurrences+=len(members)
            for w in members:windows[w]['types'][kind]+=1
            if kind=='node':
                assert not ids or ids[-1]<element['id'];ids.append(element['id']);xs.append(round(element['lon']*10000000));ys.append(round(element['lat']*10000000))
                raw_nodes+=len(json.dumps(element,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode());barriers+=int('barrier' in element['tags']);continue
            if kind!='way':continue
            points=[]
            for identity in element['nodes']:
                i=bisect_left(ids,identity);assert i<len(ids) and ids[i]==identity;points.append((xs[i]/10000000,ys[i]/10000000))
            refs+=len(points);length=0.;per=dict.fromkeys(members,0.)
            for a,b in zip(points,points[1:]):
                intervals=[]
                for w in members:
                    interval=clipped(a,b,boxes[w])
                    if interval is not None:intervals.append(interval);per[w]+=metres(a,b,*interval)
                ends=[]
                for low,high in sorted(intervals):
                    if ends and low<=ends[-1][1]:ends[-1]=(ends[-1][0],max(high,ends[-1][1]))
                    else:ends.append((low,high))
                length+=sum(metres(a,b,*v) for v in ends)
            flags,status,unit=source_flags(element['tags']);role=element['tags']['highway'];known=role in ROLES
            add(total,flags,length);add(roles[role if known else 'other'],flags,length)
            if known:add(supported,flags,length)
            for w,length in per.items():
                add(windows[w]['allCapturedHighways'],flags,length)
                if known:add(windows[w]['supportedRoadRoles'],flags,length)
            statuses[status]+=1;units[unit]+=1
    assert path.stat()==before
    expected={'rows':rows,'inputBytes':byte_count,'inputSha256':hashed.hexdigest(),'types':dict(types),'occurrences':occurrences,'wayReferences':refs,'nodeCanonicalBytes':raw_nodes,'barrierTagNodes':barriers,
              'allCapturedHighways':finish(total),'supportedRoadRoles':finish(supported),'byRole':{k:finish(v) for k,v in roles.items()},'baseSpeedStatusWays':dict(statuses),'baseSpeedUnitWays':dict(units),
              'windows':[w|{'types':dict(w['types']),'allCapturedHighways':finish(w['allCapturedHighways']),'supportedRoadRoles':finish(w['supportedRoadRoles'])} for w in windows.values()]}
    for k,v in expected.items():compare(profile[k],v,k)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
    saved=sys.argv
    try:
        sys.argv=[str(folder/'verify_attribute_inventory_controls_v1.py')]
        with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
    finally:sys.argv=saved
    from run_osm_attribute_inventory_v1 import validate,isolation
    stop=load(folder/'attribute-inventory-verifier-stop-v1.json');assert stop['verifierSha256']==sha(folder/'verify_attribute_inventory_run_v1.py') and not stop['localProofPassed']
    plan=load(folder/'attribute-inventory-plan-run-v1.json');validate(plan);freeze=load(folder/'attribute-inventory-freeze-run-v1.json')
    assert sha(folder/'attribute-inventory-plan-run-v1.json')==freeze['recipeSha256']=='a406a2202962e8e20fcbfa20768534b4b5a507d30c715a2d5517cca91a7843db'
    for name,pin in plan['inputs'].items():
        if not name.startswith('data/'):assert sha(repo/name)==pin
    for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
    closed=load(folder/'attribute-inventory-closed-run-v1.json');raw=folder/'attribute-inventory-raw/run-v1'
    assert closed['files']==len(closed['roster'])==11 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==50152
    for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
    assert closed['closerSha256']==sha(repo/'scripts/close_osm_attribute_inventory_v1.py')
    isolation(load(raw/'container-initial.json'));state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
    assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent'] and load(folder/'attribute-inventory-cleanup-run-v1.json')['independentlyAbsent']
    metrics=load(raw/'metrics.json');assert metrics['memory.max']=='536870912' and metrics['memory.swap.max']=='0' and 'oom 0' in metrics['memory.events'] and 'oom_kill 0' in metrics['memory.events']
    assert int(metrics['memory.peak'])<=536870912 and closed['usage']['logicalBytes']<=4194304
    result=load(raw/'result.json');profile=load(raw/'inventory.json');assert result['status']=='passed_raw_metadata_inventory' and result['records']==1368072 and result['inventorySha256']==sha(raw/'inventory.json')=='bbf6ab5238a8e63af7c3399132eeac2355d3750d4ec07837f99091322af76f09'
    assert profile['types']=={'node':1123919,'relation':4900,'way':239253} and profile['occurrences']==profile['rows']==1368072 and profile['wayReferences']==1530030
    assert profile['inputBytes']==477852579 and profile['inputSha256']=='efc36dc058b198711cc2666a751c9fd60b52d37902efbb22e1cba8b5f30f91f4'
    assert not any(profile[k] for k in FALSE_FLAGS)
    assert [w['id'] for w in profile['windows']]==[w['id'] for w in plan['windows']]
    for s in [profile['allCapturedHighways'],profile['supportedRoadRoles'],*profile['byRole'].values(),*(s[k] for s in profile['windows'] for k in ('allCapturedHighways','supportedRoadRoles'))]:stats_valid(s)
    for k in COUNTS+LENGTHS:
        assert math.isclose(sum(s[k] for s in profile['byRole'].values()),profile['allCapturedHighways'][k],rel_tol=1e-12,abs_tol=1e-5)
        assert math.isclose(sum(s[k] for role,s in profile['byRole'].items() if role!='other'),profile['supportedRoadRoles'][k],rel_tol=1e-12,abs_tol=1e-5)
    assert sum(profile['baseSpeedStatusWays'].values())==sum(profile['baseSpeedUnitWays'].values())==239253
    summary=load(raw/'run-summary.json');assert summary['exitCode']==summary['networkRequests']==summary['pbfOrNativeHelperReads']==0 and summary['seconds']<=360 and result['seconds']<=300
    if args.local_assets:local_audit(plan,profile)
    print(json.dumps({'capturedWays':239253,'windows':21,'closedRecordsVerified':True,'independentLocalStatistics':args.local_assets,'workerAbsent':True,'modelChanged':False,'usableLimitOrMatchingQualified':False},indent=2))


if __name__=='__main__':main()
