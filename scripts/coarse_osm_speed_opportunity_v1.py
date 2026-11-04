"""Optimistic captured-geometry opportunity on unchanged Census midpoint weights.

This is a geometric union, not road identity, car permission, or usable limits.
"""
from array import array
from bisect import bisect_left
from collections import Counter,defaultdict
import hashlib
import math

from coarse_osm_attributes_v1 import numeric_speed,validate_record
from coarse_osm_records import strict_json
from coarse_path_features import distance_km,segment_distance_km
from coarse_timing_input import require
from coarse_timing_parquet import angle_degrees,clip_segment,interpolate

KINDS=('allGeometry','anySpeedTag','plainNumeric','unscopedNumeric')
CAPS={'sourceRecords':5000,'samples':500000,'records':2000000,'memberships':4000000,'references':4000000,
      'inputBytes':1073741824,'rowBytes':8388608,'binsPerSegment':20000,'binVisits':20000000,'comparisons':50000000}
STEP=.001


def tag_mask(tags):
    any_speed=any(k=='maxspeed' or k.startswith('maxspeed:') for k in tags)
    plain=numeric_speed(tags.get('maxspeed'))['status']=='plain_numeric'
    scoped=any(k.startswith('maxspeed:') and k not in ('maxspeed:type','maxspeed:reason') for k in tags)
    return 1|(2 if any_speed else 0)|(4 if plain else 0)|(8 if plain and not scoped else 0)


class Samples:
    def __init__(self,records,windows,caps=CAPS):
        self.points=[];self.bins=defaultdict(list);self.arcs=[];seen=set();self.windows={w['id']:w['bbox'] for w in windows}
        require(0<len(self.windows)==len(windows)<=21,'Opportunity window roster')
        require(all(len(b)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in b) and -180<=b[0]<b[2]<=180 and -85<=b[1]<b[3]<=85 for b in self.windows.values()),'Opportunity finite supported boxes')
        for record in records:
            require(len(self.arcs)<caps['sourceRecords'],'Opportunity source record cap')
            wid=record['windowId'];arc=record['arc'];key=wid,arc
            require(wid in self.windows and type(arc) is int and arc>=0 and key not in seen,'Opportunity source identity');seen.add(key)
            require(record['sourceClassKph'] in (85,105),'Opportunity original source class')
            spans=record['sourceSpans'];require(isinstance(spans,list) and spans,'Opportunity source spans')
            total=0.;first=len(self.points);box=self.windows[wid]
            for a,b,weight in spans:
                require(all(len(p)==2 and all(type(x) in (int,float) and math.isfinite(x) for x in p) and box[0]-1e-10<=p[0]<=box[2]+1e-10 and box[1]-1e-10<=p[1]<=box[3]+1e-10 for p in (a,b)),'Opportunity source coordinates')
                require(type(weight) in (int,float) and math.isfinite(weight) and weight>0,'Opportunity source weight')
                length=distance_km(a,b);require(length>0,'Opportunity degenerate source span');count=max(1,math.ceil(length/.025))
                require(len(self.points)+count<=caps['samples'],'Opportunity sample cap')
                for i in range(count):
                    point=interpolate(a,b,(i+.5)/count);ordinal=len(self.points)
                    self.points.append((point,a,b,weight/count));self.bins[wid,math.floor(point[0]/STEP),math.floor(point[1]/STEP)].append(ordinal)
                total+=weight
            require(math.isclose(total,record['sourceKm'],rel_tol=1e-12,abs_tol=1e-9),'Opportunity unchanged source km')
            self.arcs.append({'windowId':wid,'arc':arc,'sourceClassKph':record['sourceClassKph'],'sourceKm':total,'firstSample':first,'lastSample':len(self.points)})
        self.masks=bytearray(len(self.points));self.bin_visits=self.comparisons=0;self.caps=caps

    def segment(self,a,b,wid,mask,check=lambda:None):
        clipped=clip_segment(a,b,self.windows[wid])
        if clipped is None:return
        c,d=interpolate(a,b,clipped[0]),interpolate(a,b,clipped[1])
        # Same conservative angular envelope and final geometric tests as the
        # frozen forward matcher, with samples indexed instead of road segments.
        padding=.025/(110*math.cos(math.radians(max(abs(c[1]),abs(d[1])))))
        xs=range(math.floor((min(c[0],d[0])-padding)/STEP),math.floor((max(c[0],d[0])+padding)/STEP)+1)
        ys=range(math.floor((min(c[1],d[1])-padding)/STEP),math.floor((max(c[1],d[1])+padding)/STEP)+1)
        require(len(xs)*len(ys)<=self.caps['binsPerSegment'],'Opportunity segment bin cap')
        for x in xs:
            for y in ys:
                self.bin_visits+=1
                if self.bin_visits%4096==0:check()
                require(self.bin_visits<=self.caps['binVisits'],'Opportunity aggregate bin cap')
                for index in self.bins.get((wid,x,y),()):
                    # A sample already supplied by this category is not counted twice.
                    if self.masks[index]&mask==mask:continue
                    self.comparisons+=1;require(self.comparisons<=self.caps['comparisons'],'Opportunity comparison cap')
                    if self.comparisons%4096==0:check()
                    point,sa,sb,_=self.points[index]
                    if angle_degrees(sa,sb,c,d)<=15 and segment_distance_km(point,c,d)<=.025:self.masks[index]|=mask

    def results(self):
        rows=[]
        for arc in self.arcs:
            first,last=arc['firstSample'],arc['lastSample'];row={k:v for k,v in arc.items() if k not in ('firstSample','lastSample')}
            row['sampleCount']=last-first
            row['unions']={name:{'alignedKm':min(arc['sourceKm'],math.fsum(self.points[i][3] for i in range(first,last) if self.masks[i]&(1<<bit))),
                                'wholeArcOpportunityKm':0.} for bit,name in enumerate(KINDS)}
            for metric in row['unions'].values():
                metric['fraction']=min(1.,metric['alignedKm']/arc['sourceKm'])
                # Counting the whole qualifying arc is intentionally generous.
                metric['wholeArcOpportunityKm']=arc['sourceKm'] if metric['fraction']>=.8-1e-12 else 0.
            rows.append(row)
        return rows


def summarize(rows):
    total=math.fsum(row['sourceKm'] for row in rows)
    return {'arcWindowRecords':len(rows),'sourceKm':total,'samples':sum(r['sampleCount'] for r in rows),
            'unions':{name:{'alignedKm':math.fsum(r['unions'][name]['alignedKm'] for r in rows),
                            'wholeArcOpportunityKm':math.fsum(r['unions'][name]['wholeArcOpportunityKm'] for r in rows),
                            'alignedFraction':math.fsum(r['unions'][name]['alignedKm'] for r in rows)/total if total else None,
                            'wholeArcOpportunityFraction':math.fsum(r['unions'][name]['wholeArcOpportunityKm'] for r in rows)/total if total else None} for name in KINDS}}


def opportunity(stream,source_records,*,snapshot,windows,caps=CAPS,check=lambda:None):
    require(set(caps)==set(CAPS) and all(type(v) is int and 0<v<=CAPS[k] for k,v in caps.items()),'Opportunity exact finite caps')
    samples=Samples(source_records,windows,caps);ids=array('q');xs=array('i');ys=array('i')
    rows=byte_count=memberships=references=0;types=Counter();mask_counts=Counter();hashed=hashlib.sha256();last=None
    while line:=stream.readline(caps['rowBytes']+1):
        check();rows+=1;byte_count+=len(line)
        require(len(line)<=caps['rowBytes'] and line.endswith(b'\n') and rows<=caps['records'] and byte_count<=caps['inputBytes'],'Opportunity captured input caps')
        hashed.update(line);record=strict_json(line);element=validate_record(record,snapshot);key=element['type'],element['id']
        require(last is None or last<key,'Opportunity captured typed order');last=key;types[key[0]]+=1
        members=record['windowIds'];require(all(w in samples.windows for w in members),'Opportunity unknown window');memberships+=len(members);require(memberships<=caps['memberships'],'Opportunity membership cap')
        if key[0]=='node':
            require(not ids or ids[-1]<key[1],'Opportunity node order')
            x,y=round(element['lon']*1e7),round(element['lat']*1e7);require(x/1e7==element['lon'] and y/1e7==element['lat'],'Opportunity native coordinate precision')
            ids.append(key[1]);xs.append(x);ys.append(y);continue
        if key[0]!='way':continue
        refs=element['nodes'];require(2<=len(refs)<=65536,'Opportunity way reference count');references+=len(refs);require(references<=caps['references'],'Opportunity reference cap')
        mask=tag_mask(element['tags']);mask_counts[str(mask)]+=1;previous=None
        for i,identity in enumerate(refs):
            if i%1024==0:check()
            index=bisect_left(ids,identity);require(index<len(ids) and ids[index]==identity,'Opportunity missing node');point=[xs[index]/1e7,ys[index]/1e7]
            if previous is not None:
                for wid in members:samples.segment(previous,point,wid,mask,check)
            previous=point
    check();arc_rows=samples.results()
    report={'format':'native-osm-speed-geometry-opportunity-v1','rows':rows,'inputBytes':byte_count,'inputSha256':hashed.hexdigest(),'types':dict(types),'memberships':memberships,'references':references,
            'rawWayCategoryMaskCounts':dict(mask_counts),'binVisits':samples.bin_visits,'comparisons':samples.comparisons,'sampleMasksSha256':hashlib.sha256(samples.masks).hexdigest(),
            'allWindows':summarize(arc_rows),'classes':{str(k):summarize([r for r in arc_rows if r['sourceClassKph']==k]) for k in (85,105)},
            'windows':[{'id':w['id'],'totals':summarize([r for r in arc_rows if r['windowId']==w['id']]),'classes':{str(k):summarize([r for r in arc_rows if r['windowId']==w['id'] and r['sourceClassKph']==k]) for k in (85,105)}} for w in windows],
            'sourceAdequacyQualified':False,'carPermissionReviewed':False,'uniqueMatchesQualified':False,'usableLimitOrMatchingQualified':False,'modelChanged':False,
            'scope':'Captured geometry only; all original weighted Census midpoints,25m/15degree geometric unions,80%whole-arc opportunity. AnySpeedTag includes symbolic/scoped/annotation tags. Even plain numeric subsets ignore access/direction/grade/conflicts/identity. No independent usable limit, unique road/connected route, national completeness, physical route or timing accuracy.'}
    return report,arc_rows,bytes(samples.masks)
