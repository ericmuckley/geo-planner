"""Raw tag/geometry presence over every captured record; never driving costs."""
from array import array
from bisect import bisect_left
from collections import Counter
import hashlib
import math

from coarse_osm_attributes_v1 import ANNOTATIONS,ROAD_ROLES,ACCESS,family,numeric_speed,validate_record
from coarse_osm_records import canonical,strict_json
from coarse_timing_parquet import clip_segment,interpolate
from coarse_path_features import distance_km
from coarse_timing_input import require

SCALE=10000000
ROLES=sorted(ROAD_ROLES|{r+'_link' for r in ('motorway','trunk','primary','secondary','tertiary')})
CAPS={'records':2000000,'occurrences':4000000,'inputBytes':1073741824,'recordBytes':8388608,'wayReferences':4000000,'nodeCanonicalBytes':268435456}


class Nodes:
    def __init__(self,limit,max_nodes):
        self.data=bytearray(limit);self.ids=array('q');self.x=array('i');self.y=array('i');self.offsets=array('I',[0]);self.max_nodes=max_nodes
        require(self.ids.itemsize==8 and self.x.itemsize==4 and self.offsets.itemsize==4,'Inventory native word widths')

    def add(self,element):
        identity=element['id'];require(len(self.ids)<self.max_nodes and (not self.ids or self.ids[-1]<identity),'Inventory node count/order')
        x,y=round(element['lon']*SCALE),round(element['lat']*SCALE)
        require(x/SCALE==element['lon'] and y/SCALE==element['lat'],'Inventory native coordinate precision')
        raw=canonical(element);start=self.offsets[-1];end=start+len(raw);require(end<=len(self.data),'Inventory node arena cap')
        self.data[start:end]=raw;self.ids.append(identity);self.x.append(x);self.y.append(y);self.offsets.append(end)

    def get(self,identity):
        require(type(identity) is int and 0<identity<2**63,'Inventory reference identity')
        index=bisect_left(self.ids,identity);require(index<len(self.ids) and self.ids[index]==identity,'Inventory missing geometry node')
        return [self.x[index]/SCALE,self.y[index]/SCALE],memoryview(self.data)[self.offsets[index]:self.offsets[index+1]]


def merged(intervals):
    if not intervals:return []
    result=[]
    for low,high in sorted(intervals):
        if result and low<=result[-1][1]:result[-1]=(result[-1][0],max(high,result[-1][1]))
        else:result.append((low,high))
    return result


def empty():
    return dict(ways=0,clippedMeters=0.,plainNumericWays=0,plainNumericMeters=0.,unscopedNumericWays=0,unscopedNumericMeters=0.,speedScopeWays=0,accessTagWays=0,conditionalAccessWays=0,directionTagWays=0)


def flags(tags):
    speed=numeric_speed(tags.get('maxspeed'));scopes=any(k.startswith('maxspeed:') and k not in ANNOTATIONS for k in tags)
    access=family(tags,ACCESS)
    return {'plain':speed['status']=='plain_numeric','unscoped':speed['status']=='plain_numeric' and not scopes,
            'scopes':scopes,'access':bool(access),'conditionalAccess':any(k.endswith(':conditional') for k in access),
            'direction':bool(family(tags,('oneway',))),'speedStatus':speed['status'],'unit':speed['sourceUnit'] or 'unknown'}


def tally(stats,values,meters):
    require(math.isfinite(meters) and meters>=0,'Inventory finite geometry length');stats['ways']+=1;stats['clippedMeters']+=meters
    for flag,count,length in [('plain','plainNumericWays','plainNumericMeters'),('unscoped','unscopedNumericWays','unscopedNumericMeters')]:
        if values[flag]:stats[count]+=1;stats[length]+=meters
    for flag,key in [('scopes','speedScopeWays'),('access','accessTagWays'),('conditionalAccess','conditionalAccessWays'),('direction','directionTagWays')]:stats[key]+=int(values[flag])


def finish(stats):
    return stats|{'plainNumericLengthFraction':stats['plainNumericMeters']/stats['clippedMeters'] if stats['clippedMeters'] else None,
                  'unscopedNumericLengthFraction':stats['unscopedNumericMeters']/stats['clippedMeters'] if stats['clippedMeters'] else None}


def inventory(stream,*,snapshot,windows,caps=CAPS,check=lambda:None):
    require(set(caps)==set(CAPS) and all(type(v) is int and 0<v<=CAPS[k] for k,v in caps.items()),'Inventory exact finite cap schema')
    boxes={}
    require(0<len(windows)<=21,'Inventory window count')
    for window in windows:
        name=window['id'];box=window['bbox'];require(isinstance(name,str) and 0<len(name)<=128 and name not in boxes,'Inventory window identity')
        require(len(box)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in box) and -180<=box[0]<box[2]<=180 and -90<=box[1]<box[3]<=90,'Inventory window bounds');boxes[name]=box
    nodes=Nodes(caps['nodeCanonicalBytes'],caps['records']);all_stats=empty();supported=empty();roles={r:empty() for r in [*ROLES,'other']}
    per_window={w:{'all':empty(),'supportedRoadRoles':empty(),'types':Counter()} for w in boxes}
    types=Counter();speed_status=Counter();units=Counter();rows=byte_count=occurrences=references=barrier_nodes=0;last=None;hashed=hashlib.sha256()
    while line:=stream.readline(caps['recordBytes']+1):
        check();require(line.endswith(b'\n') and len(line)<=caps['recordBytes'],'Inventory row byte cap/termination')
        rows+=1;byte_count+=len(line);require(rows<=caps['records'] and byte_count<=caps['inputBytes'],'Inventory input/record cap');hashed.update(line)
        record=strict_json(line);element=validate_record(record,snapshot);key=element['type'],element['id']
        require(last is None or last<key,'Inventory typed order/duplicate');last=key
        memberships=record['windowIds'];require(all(w in boxes for w in memberships),'Inventory unknown window');occurrences+=len(memberships);require(occurrences<=caps['occurrences'],'Inventory membership cap')
        types[key[0]]+=1
        for name in memberships:per_window[name]['types'][key[0]]+=1
        if key[0]=='node':nodes.add(element);barrier_nodes+=int('barrier' in element['tags']);continue
        if key[0]!='way':continue
        tags=element['tags'];role=tags.get('highway');require(isinstance(role,str) and bool(role),'Inventory nonempty highway')
        refs=element['nodes'];require(2<=len(refs)<=65536,'Inventory ordered reference count');references+=len(refs);require(references<=caps['wayReferences'],'Inventory reference cap')
        geometry=hashlib.sha256(b'['+canonical(snapshot)+b',[');previous=None;meters=0.;window_meters=dict.fromkeys(memberships,0.)
        for index,identity in enumerate(refs):
            if index%1024==0:check()
            point,raw=nodes.get(identity)
            if index:geometry.update(b',')
            geometry.update(raw)
            if previous is not None:
                intervals=[]
                for name in memberships:
                    interval=clip_segment(previous,point,boxes[name])
                    if interval is not None:
                        intervals.append(interval);window_meters[name]+=1000*distance_km(interpolate(previous,point,interval[0]),interpolate(previous,point,interval[1]))
                for low,high in merged(intervals):meters+=1000*distance_km(interpolate(previous,point,low),interpolate(previous,point,high))
            previous=point
        geometry.update(b']]');require(geometry.hexdigest()==record.get('geometryDependencySha256'),'Inventory geometry dependency mismatch')
        values=flags(tags);recognized=role in ROLES;tally(all_stats,values,meters);tally(roles[role if recognized else 'other'],values,meters)
        if recognized:tally(supported,values,meters)
        for name,length in window_meters.items():
            tally(per_window[name]['all'],values,length)
            if recognized:tally(per_window[name]['supportedRoadRoles'],values,length)
        speed_status[values['speedStatus']]+=1;units[values['unit']]+=1
    check()
    return {'format':'native-osm-raw-metadata-inventory-v1','rows':rows,'inputBytes':byte_count,'inputSha256':hashed.hexdigest(),'types':dict(types),
            'occurrences':occurrences,'wayReferences':references,'nodeCanonicalBytes':nodes.offsets[-1],'barrierTagNodes':barrier_nodes,
            'allCapturedHighways':finish(all_stats),'supportedRoadRoles':finish(supported),'byRole':{r:finish(s) for r,s in roles.items()},
            'windows':[{'id':w,'types':dict(s['types']),'allCapturedHighways':finish(s['all']),'supportedRoadRoles':finish(s['supportedRoadRoles'])} for w,s in per_window.items()],
            'baseSpeedStatusWays':dict(speed_status),'baseSpeedUnitWays':dict(units),'sourceOrPublisherAdequacyQualified':False,
            'permissionsReviewed':False,'usableForTiming':False,'usableLimitOrMatchingGateQualified':False,'modelChanged':False,
            'scope':'Raw tag presence over all captured ways; spherical clipped-polyline metres (radius6371km), unioned across overlapping windows. Not reviewed car permission, legal/applicable speed coverage, matched-route coverage, timing costs or national accuracy.'}
