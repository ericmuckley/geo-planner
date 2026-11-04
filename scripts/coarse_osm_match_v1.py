"""Native OSM junction/geometry adapter for acquired-file connected candidates.

Attributes remain native and unreviewed; generic geometry helpers receive only
coordinates, node identities, and part ordinals, never Overture attribute rows.
"""
from collections import Counter,defaultdict
import hashlib
import math

from coarse_osm_attributes_v1 import ROAD_ROLES,ANNOTATIONS,ACCESS,family,numeric_speed,validate_record
from coarse_osm_attribute_inventory_v1 import Nodes as QualifiedNodes
from coarse_osm_records import strict_json,canonical
from coarse_path_features import distance_km,segment_distance_km
from coarse_timing_chains import make_nodes
from coarse_timing_fragments import make_fragments,search_fragments
from coarse_timing_input import require
from coarse_timing_parquet import angle_degrees,clip_segment,interpolate

CAPS={'nodeCanonicalBytes':268435456,'geometryReferences':4000000,'inputBytes':1073741824,'rowBytes':8388608,'records':2000000,'windowWays':100000,'windowReferences':1000000,'parts':300000,
      'indexSegments':1000000,'binEntries':8000000,'comparisons':50000000,'arcSamples':20000,'sampleMemberships':2000000,
      'projectionComparisons':4000000,'searchRows':64,'searchStates':4096}
ROLES=ROAD_ROLES|{r+'_link' for r in ('motorway','trunk','primary','secondary','tertiary')}


def attributes(tags):
    speed=numeric_speed(tags.get('maxspeed'));scopes={k:v for k,v in tags.items() if k.startswith('maxspeed:') and k not in ANNOTATIONS}
    return {'speed':speed,'speedScopeTags':scopes,'unscopedNumeric':speed['status']=='plain_numeric' and not scopes,
            'accessTags':family(tags,ACCESS),'directionTags':family(tags,('oneway',)),
            'structureTags':family(tags,('bridge','tunnel','layer','level','location','junction','construction','proposed')),
            'carPermission':'unreviewed','usableForTiming':False}


class Nodes(QualifiedNodes):
    def __init__(self,caps):
        super().__init__(caps['nodeCanonicalBytes'],caps['records']);self.barriers=set()
    def add(self,e):
        super().add(e)
        if 'barrier' in e['tags']:self.barriers.add(e['id'])
    def point(self,identity):return self.get(identity)[0]


def read_nodes(stream,snapshot,check=lambda:None,caps=CAPS):
    nodes=Nodes(caps);references=0;hashed=hashlib.sha256();rows=byte_count=memberships=0;types=Counter();last=None
    while line:=stream.readline(caps['rowBytes']+1):
        check();rows+=1;byte_count+=len(line);require(len(line)<=caps['rowBytes'] and line.endswith(b'\n') and rows<=caps['records'] and byte_count<=caps['inputBytes'],'Native matcher captured input cap')
        hashed.update(line);record=strict_json(line);e=validate_record(record,snapshot);key=e['type'],e['id'];require(last is None or last<key,'Native matcher typed order');last=key;types[key[0]]+=1;memberships+=len(record['windowIds'])
        if key[0]=='node':nodes.add(e)
        elif key[0]=='way':
            refs=e['nodes'];references+=len(refs);require(2<=len(refs)<=65536 and references<=caps['geometryReferences'],'Native matcher geometry reference cap')
            geometry=hashlib.sha256(b'['+canonical(snapshot)+b',[')
            for i,identity in enumerate(refs):
                if i%1024==0:check()
                if i:geometry.update(b',')
                _,raw=nodes.get(identity);geometry.update(raw)
            geometry.update(b']]');require(geometry.hexdigest()==record.get('geometryDependencySha256'),'Native matcher geometry dependency drift')
    return nodes,{'rows':rows,'bytes':byte_count,'sha256':hashed.hexdigest(),'types':dict(types),'memberships':memberships}


def read_window(stream,nodes,wid,check=lambda:None,caps=CAPS):
    ways=[];used=Counter();hashed=hashlib.sha256();rows=byte_count=references=0
    while line:=stream.readline(caps['rowBytes']+1):
        check();rows+=1;byte_count+=len(line);require(len(line)<=caps['rowBytes'] and line.endswith(b'\n') and rows<=caps['records'] and byte_count<=caps['inputBytes'],'Native matcher window input cap');hashed.update(line)
        # The complete stream was normalized by read_nodes and is rebound below.
        # Canonical type tokens avoid parsing unrelated nodes on every window.
        if b'"type":"way"' not in line:continue
        record=strict_json(line);e=record['element']
        if e['type']!='way' or wid not in record['windowIds']:continue
        refs=e['nodes'];require(2<=len(refs)<=65536 and len(ways)<caps['windowWays'],'Native matcher selected way cap')
        references+=len(refs);require(references<=caps['windowReferences'],'Native matcher window reference cap');used.update(refs)
        ways.append({'id':e['id'],'version':e['version'],'refs':refs,'tags':e['tags'],'elementSha256':record['elementSha256'],'geometryDependencySha256':record['geometryDependencySha256'],'rawLineSha256':hashlib.sha256(line).hexdigest()})
    metadata=[];lines=[]
    for way in ways:
        check();refs=way['refs'];cuts=[0,*[i for i in range(1,len(refs)-1) if used[refs[i]]>1],len(refs)-1]
        for first,last in zip(cuts,cuts[1:]):
            require(len(metadata)<caps['parts'],'Native matcher native part cap');line=[nodes.point(ref) for ref in refs[first:last+1]];ordinal=len(metadata)
            reasons=[]
            if way['tags'].get('highway') not in ROLES:reasons.append('unsupported_native_road_role')
            if refs[first]==refs[last]:reasons.append('same_native_endpoint_identity')
            if not any(a!=b for a,b in zip(line,line[1:])):reasons.append('degenerate_native_geometry')
            metadata.append({'ordinal':ordinal,'nativeWayId':way['id'],'nativeWayVersion':way['version'],'firstNodeIndex':first,'lastNodeIndex':last,
                             'elementSha256':way['elementSha256'],'geometryDependencySha256':way['geometryDependencySha256'],'rawLineSha256':way['rawLineSha256'],
                             'endpointIds':[refs[first],refs[last]],'endpoints':[line[0],line[-1]],'baseReasons':reasons,'nativeTags':way['tags'],'attributes':attributes(way['tags'])|{'barrierNodeIds':[ref for ref in refs[first:last+1] if ref in nodes.barriers]}})
            lines.append(line)
    return metadata,lines,{'rows':rows,'bytes':byte_count,'sha256':hashed.hexdigest(),'ways':len(ways),'references':references,'parts':len(metadata),'sharedNativeNodes':sum(n>1 for n in used.values())}


class Index:
    def __init__(self,lines,box,check=lambda:None,caps=CAPS):
        self.segments=[];self.bins=defaultdict(list);self.caps=caps;self.comparisons=0;entries=0
        for ordinal,line in enumerate(lines):
            check()
            for a,b in zip(line,line[1:]):
                clipped=clip_segment(a,b,box)
                if clipped is None:continue
                c,d=interpolate(a,b,clipped[0]),interpolate(a,b,clipped[1]);padding=.025/(110*math.cos(math.radians(max(abs(c[1]),abs(d[1])))))
                xs=range(math.floor((min(c[0],d[0])-padding)/.01),math.floor((max(c[0],d[0])+padding)/.01)+1);ys=range(math.floor((min(c[1],d[1])-padding)/.01),math.floor((max(c[1],d[1])+padding)/.01)+1)
                entries+=len(xs)*len(ys);require(entries<=caps['binEntries'] and len(self.segments)<caps['indexSegments'],'Native matcher index cap');sid=len(self.segments);self.segments.append((ordinal,c,d))
                for x in xs:
                    for y in ys:self.bins[x,y].append(sid)
        self.entries=entries

    def support(self,spans,check=lambda:None):
        samples=[];points=[];tangents=[];weights=[];memberships=0
        for si,(a,b,km) in enumerate(spans):
            require(type(km) in (int,float) and math.isfinite(km) and km>0,'Native matcher source span weight');count=max(1,math.ceil(distance_km(a,b)/.025));require(len(samples)+count<=self.caps['arcSamples'],'Native matcher arc sample cap')
            for i in range(count):
                check();point=interpolate(a,b,(i+.5)/count);found=set()
                for sid in self.bins.get((math.floor(point[0]/.01),math.floor(point[1]/.01)),()):
                    self.comparisons+=1;require(self.comparisons<=self.caps['comparisons'],'Native matcher comparison cap');ordinal,c,d=self.segments[sid]
                    if angle_degrees(a,b,c,d)<=15 and segment_distance_km(point,c,d)<=.025:found.add(ordinal)
                memberships+=len(found);require(memberships<=self.caps['sampleMemberships'],'Native matcher sample membership cap')
                samples.append([si,i,count,km/count,sorted(found)]);points.append(point);tangents.append([a,b]);weights.append(km/count)
        return samples,points,tangents,weights


def match(record,metadata,lines,index,box,check=lambda:None,caps=CAPS):
    samples,points,tangents,weights=index.support(record['sourceSpans'],check);require(math.isclose(math.fsum(weights),record['sourceKm'],rel_tol=1e-12,abs_tol=1e-9),'Native matcher original denominator')
    aligned=Counter(ordinal for sample in samples for ordinal in sample[4]);projection=sum(n*max(0,len(lines[ordinal])-1) for ordinal,n in aligned.items())
    base={'windowId':record['windowId'],'arc':record['arc'],'sourceClassKph':record['sourceClassKph'],'sourceKm':record['sourceKm'],'sampleCount':len(samples),'sampleMemberships':sum(aligned.values()),'alignedNativeParts':len(aligned),'projectionComparisonsBound':projection,
          'sourceAdequacyQualified':False,'carPermissionReviewed':False,'uniquePhysicalMatchQualified':False,'usableLimitOrMatchingQualified':False,'modelChanged':False}
    if projection>caps['projectionComparisons']:
        return base|{'status':'projection_cap','candidates':[],'unrepresentedParts':sorted(aligned),'searchCapped':True,'capReasons':['projection_comparisons'],'expandedStates':0}
    full,_=make_nodes(metadata,samples,points,box)
    fragments,issues,_=make_fragments(metadata,lines,samples,points,tangents,box,list(full.values()),check)
    search=search_fragments(fragments,weights,maximum_rows=caps['searchRows'],maximum_states=caps['searchStates'],check=check)
    represented={n['ordinal'] for n in fragments.values()};unrepresented=sorted(set(aligned)-represented)
    grouped={}
    for candidate in search['candidates']:
        path=tuple(candidate['rowOrdinals']);key=min(path,path[::-1]);group=grouped.setdefault(key,{'nativeParts':list(key),'variants':[],'maximumSupportedKm':0.,'allUnscopedNumeric':all(metadata[i]['attributes']['unscopedNumeric'] for i in key)})
        group['variants'].append(candidate);group['maximumSupportedKm']=max(group['maximumSupportedKm'],candidate['supportedKm'])
    status='search_capped' if search['searchCapped'] else 'unresolved_aligned_alternatives' if unrepresented else 'single_acquired_file_geometric_path' if len(grouped)==1 else 'multiple_acquired_file_geometric_paths' if grouped else 'no_path_under_fragment_rules'
    # Native tags are retained only for aligned parts; every source/raw seal binds
    # them to the complete immutable capture rather than a converted road schema.
    bindings=[metadata[i] for i in sorted(aligned)]
    return base|{'status':status,'candidates':list(grouped.values()),'alignedPartBindings':bindings,'unrepresentedParts':unrepresented,'fragmentIssues':issues,
                 'searchCapped':search['searchCapped'],'capReasons':search['capReasons'],'expandedStates':search['expandedStates']}


def summary(records):
    total=math.fsum(r['sourceKm'] for r in records)
    single=[r for r in records if r['status']=='single_acquired_file_geometric_path']
    potential=math.fsum(r['candidates'][0]['maximumSupportedKm'] for r in single if r['candidates'][0]['allUnscopedNumeric'])
    return {'arcWindowRecords':len(records),'sourceKm':total,'samples':sum(r['sampleCount'] for r in records),'statusCounts':dict(Counter(r['status'] for r in records)),
            'statusSourceKm':{s:math.fsum(r['sourceKm'] for r in records if r['status']==s) for s in sorted({r['status'] for r in records})},
            'singleGeometricPathRecords':len(single),'singlePathUnscopedNumericSupportedKm':potential,'singlePathUnscopedNumericFraction':potential/total if total else None,
            'cappedRecords':sum(r['searchCapped'] for r in records),'usableLimitOrMatchingQualified':False,'modelChanged':False}
