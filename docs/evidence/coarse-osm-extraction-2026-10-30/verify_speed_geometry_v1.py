"""Independent full-mask geometry audit of the closed opportunity diagnostic.

Only --local-assets streams the derived captured JSONL and original saved
Census spans. No worker, PBF, fine index, database, network, or producer call.
"""
import argparse
from array import array
from bisect import bisect_left
from collections import defaultdict
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import re
import runpy
import sys
import time

folder=Path(__file__).resolve().parent;repo=folder.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())


def mask(tags):
    raw=tags.get('maxspeed');plain=False
    if raw is not None and len(raw)<=256:
        match=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)(?: (mph|km/h))?',raw)
        if match:
            value=float(match[1])*(1.609344 if match[2]=='mph' else 1)
            plain=value>0 and math.isfinite(value)
    scoped=any(k.startswith('maxspeed:') and k not in {'maxspeed:type','maxspeed:reason'} for k in tags)
    return 1|(2 if any(k=='maxspeed' or k.startswith('maxspeed:') for k in tags) else 0)|(4 if plain else 0)|(8 if plain and not scoped else 0)


def clip(a,b,box):
    low,high=0.,1.
    for axis in (0,1):
        delta=b[axis]-a[axis]
        if delta==0:
            if not box[axis]<=a[axis]<=box[axis+2]:return None
        else:
            lo=(box[axis]-a[axis])/delta;hi=(box[axis+2]-a[axis])/delta
            low=max(low,min(lo,hi));high=min(high,max(lo,hi))
            if high<=low:return None
    return ([a[i]+low*(b[i]-a[i]) for i in (0,1)],[a[i]+high*(b[i]-a[i]) for i in (0,1)])


def distance(a,b):
    lat1,lat2=map(math.radians,(a[1],b[1]));h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(b[0]-a[0])/2)**2
    return 12742*math.atan2(math.sqrt(min(1,h)),math.sqrt(max(0,1-h)))


def aligned(point,sa,sb,a,b):
    scale=math.cos(math.radians((sa[1]+sb[1]+a[1]+b[1])/4));ux=(sb[0]-sa[0])*scale;uy=sb[1]-sa[1];vx=(b[0]-a[0])*scale;vy=b[1]-a[1];den=math.hypot(ux,uy)*math.hypot(vx,vy)
    if not den or abs(ux*vx+uy*vy)/den<math.cos(math.radians(15)):return False
    scale=math.cos(math.radians(point[1]));dx=(b[0]-a[0])*scale;dy=b[1]-a[1];den=dx*dx+dy*dy
    t=0 if not den else max(0,min(1,((point[0]-a[0])*scale*dx+(point[1]-a[1])*dy)/den))
    return distance(point,[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])])<=.025


def audit():
    began=time.monotonic();plan=load(folder/'speed-opportunity-plan-run-v1.json');raw=folder/'speed-opportunity-raw/run-v1';expected=(raw/'sample-masks.bin').read_bytes()
    original=repo/'data/coarse-quality/overture-timing-cache-analysis-v2/matches.jsonl';assert sha(original)==plan['inputs'][str(original.relative_to(repo))]
    source=[json.loads(line) for line in original.read_bytes().splitlines()];points=[];bins=defaultdict(list);step=.002;boxes={w['id']:w['bbox'] for w in plan['windows']}
    for record in source:
        for a,b,km in record['sourceSpans']:
            count=max(1,math.ceil(distance(a,b)/.025))
            for i in range(count):
                fraction=(i+.5)/count;p=[a[j]+fraction*(b[j]-a[j]) for j in (0,1)];index=len(points);points.append((p,a,b));bins[record['windowId'],math.floor(p[0]/step),math.floor(p[1]/step)].append(index)
    assert len(points)==len(expected)<=500000
    actual=bytearray(len(points));ids=array('q');xs=array('i');ys=array('i');hashed=hashlib.sha256();rows=refs=checks=visits=0
    path=repo/'data/coarse-quality/us-osm-disk-capture-run-v1/extract/elements.jsonl';before=path.stat();assert before.st_size==477852579
    with path.open('rb') as stream:
        for line in stream:
            assert len(line)<=8388608;hashed.update(line);rows+=1;record=json.loads(line);element=record['element']
            if element['type']=='node':
                assert not ids or element['id']>ids[-1];ids.append(element['id']);xs.append(round(element['lon']*1e7));ys.append(round(element['lat']*1e7));continue
            if element['type']!='way':continue
            category=mask(element['tags']);previous=None
            for identity in element['nodes']:
                refs+=1;index=bisect_left(ids,identity);assert index<len(ids) and ids[index]==identity;point=(xs[index]/1e7,ys[index]/1e7)
                if previous is not None:
                    for wid in record['windowIds']:
                        segment=clip(previous,point,boxes[wid])
                        if segment is None:continue
                        a,b=segment;padding=.025/(110*math.cos(math.radians(max(abs(a[1]),abs(b[1])))))
                        xr=range(math.floor((min(a[0],b[0])-padding)/step),math.floor((max(a[0],b[0])+padding)/step)+1);yr=range(math.floor((min(a[1],b[1])-padding)/step),math.floor((max(a[1],b[1])+padding)/step)+1)
                        assert len(xr)*len(yr)<=20000
                        for x in xr:
                            for y in yr:
                                visits+=1;assert visits<=20000000
                                for sample in bins.get((wid,x,y),()):
                                    if actual[sample]&category==category:continue
                                    checks+=1;assert checks<=50000000
                                    p,sa,sb=points[sample]
                                    if aligned(p,sa,sb,a,b):actual[sample]|=category
                previous=point
            assert time.monotonic()-began<300
    assert path.stat()==before and hashed.hexdigest()==plan['inputs'][str(path.relative_to(repo))]
    assert rows==1368072 and refs==1530030
    assert actual==expected,{'differentMasks':sum(a!=b for a,b in zip(actual,expected))}
    return {'completeIndependentMaskAudit':True,'midpoints':len(actual),'sourceArcWindowRecords':len(source),'capturedRows':rows,'wayReferences':refs,'inputSha256':hashed.hexdigest(),'sampleMasksSha256':hashlib.sha256(actual).hexdigest(),'auditorSha256':sha(Path(__file__)),'oracleBinStepDegrees':step,'binVisits':visits,'comparisons':checks,'seconds':time.monotonic()-began,'pbfReads':0,'networkRequests':0,'modelChanged':False,'usableLimitOrMatchingQualified':False,'method':'Separate slab clipping, dot/cos tangent, projection/atan2 haversine, distinct reverse bin size and numeric-tag classification; full saved midpoint masks compared. Original spans and closed input shared. No physical road identity/access/source adequacy proof.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');parser.add_argument('--record',action='store_true');args=parser.parse_args()
    assert not args.record or args.local_assets
    saved=sys.argv
    try:
        sys.argv=[str(folder/'verify_speed_opportunity_v1.py'),'--stage','run']
        with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
    finally:sys.argv=saved
    if args.local_assets:
        result=audit()
        if args.record:
            with (folder/'speed-opportunity-independent-geometry-v1.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    else:
        result=load(folder/'speed-opportunity-independent-geometry-v1.json');assert result['auditorSha256']==sha(Path(__file__)) and result['completeIndependentMaskAudit']
        assert result['sampleMasksSha256']==sha(folder/'speed-opportunity-raw/run-v1/sample-masks.bin')
    print(json.dumps(result,indent=2))
