"""Continuous source progress for short native junction geometry candidates.

Original positive Census midpoint weights and25m/15degree/80%criteria remain.
Additional native geometry probes carry no Census weight or car permission.
"""
from collections import defaultdict
import math

from coarse_osm_match_v1 import CAPS as BASE_CAPS,Index,ROLES,read_nodes,read_window
from coarse_path_features import distance_km,segment_distance_km
from coarse_timing_fragments import cumulative_lengths,nearest_projection,point_at,search_fragments
from coarse_timing_input import PilotError,require
from coarse_timing_parquet import angle_degrees,interpolate

CAPS=BASE_CAPS|{'nearbyParts':20000,'curveSamples':20000}
TIE=1e-9


class GeometryRejected(Exception):pass
class ProjectionCap(Exception):pass


class Work:
    def __init__(self,cap,check):self.used=0;self.cap=cap;self.check=check
    def charge(self,n):
        self.used+=n
        if self.used>self.cap:raise ProjectionCap()
        self.check()


class Source:
    def __init__(self,spans,work):
        self.spans=spans;self.work=work;self.starts=[];self.lengths=[];total=0.
        for a,b,_ in spans:
            length=distance_km(a,b);require(length>0,'Continuous nondegenerate source span');self.starts.append(total);self.lengths.append(length);total+=length
        self.total=total

    def project(self,point,tangent):
        self.work.charge(len(self.spans));found=[]
        for i,(a,b,_) in enumerate(self.spans):
            scale=math.cos(math.radians(point[1]));dx=(b[0]-a[0])*scale;dy=b[1]-a[1];den=dx*dx+dy*dy
            t=0 if not den else max(0.,min(1.,((point[0]-a[0])*scale*dx+(point[1]-a[1])*dy)/den));q=interpolate(a,b,t)
            found.append((distance_km(point,q),self.starts[i]+t*self.lengths[i],a,b))
        nearest=min(row[0] for row in found)
        if nearest>.025:raise GeometryRejected('outside_source_corridor')
        tied=[row for row in found if row[0]-nearest<=TIE]
        if max(row[1] for row in tied)-min(row[1] for row in tied)>TIE:raise GeometryRejected('ambiguous_source_progress')
        # Adjacent source spans may share the same geometric vertex/progress.
        # Either incident tangent can describe an arriving/departing native part.
        if not any(angle_degrees(*tangent,row[2],row[3])<=15 for row in tied):raise GeometryRejected('source_tangent_mismatch')
        return min(row[1] for row in tied)


def nearby_parts(index,spans,caps,check):
    result=set()
    for a,b,_ in spans:
        check();pad=.025/(110*math.cos(math.radians(max(abs(a[1]),abs(b[1])))))
        xs=range(math.floor((min(a[0],b[0])-pad)/.01),math.floor((max(a[0],b[0])+pad)/.01)+1);ys=range(math.floor((min(a[1],b[1])-pad)/.01),math.floor((max(a[1],b[1])+pad)/.01)+1)
        require(len(xs)*len(ys)<=caps['binEntries'],'Continuous source bin envelope')
        for x in xs:
            for y in ys:
                for sid in index.bins.get((x,y),()):result.add(index.segments[sid][0])
                if len(result)>caps['nearbyParts']:raise ProjectionCap()
    return result


def interval_curve(line,lengths,low,high,box,source,caps):
    lo,hi=low*lengths[-1],high*lengths[-1];projections=[];count=0
    for i,(a,b) in enumerate(zip(line,line[1:])):
        length=lengths[i+1]-lengths[i]
        if not length:continue
        start=max(lo,lengths[i]);end=min(hi,lengths[i+1])
        if end<=start:continue
        c,d=interpolate(a,b,(start-lengths[i])/length),interpolate(a,b,(end-lengths[i])/length)
        if not all(box[0]<=p[0]<=box[2] and box[1]<=p[1]<=box[3] for p in (c,d)):raise GeometryRejected('outside_original_window')
        n=max(1,math.ceil(distance_km(c,d)/.025));count+=n+2
        if count>caps['curveSamples']:raise ProjectionCap()
        for t in [0.,*[(j+.5)/n for j in range(n)],1.]:projections.append(source.project(interpolate(c,d,t),(c,d)))
    if not projections or abs(projections[-1]-projections[0])<=TIE:raise GeometryRejected('nonprogressing_native_curve')
    direction=int(projections[-1]<projections[0]);deltas=[b-a for a,b in zip(projections,projections[1:])]
    if not (all(d>=-TIE for d in deltas) if not direction else all(d<=TIE for d in deltas)):raise GeometryRejected('nonmonotone_source_progress')
    return direction,min(projections[0],projections[-1]),max(projections[0],projections[-1])


def fragments(metadata,lines,index,record,samples,points,box,check,caps):
    work=Work(caps['projectionComparisons'],check);source=Source(record['sourceSpans'],work);nearby=nearby_parts(index,record['sourceSpans'],caps,check)
    aligned=defaultdict(list)
    for i,sample in enumerate(samples):
        for ordinal in sample[4]:aligned[ordinal].append(i)
    nodes={};issues=[]
    for ordinal in sorted(nearby):
        check();meta=metadata[ordinal];line=lines[ordinal];indices=aligned.get(ordinal,[]);rejected=[]
        if meta['endpointIds'][0]==meta['endpointIds'][1]:
            issues.append({'ordinal':ordinal,'reasons':['closed_native_part_unresolved']});continue
        try:lengths=cumulative_lengths(line)
        except PilotError:
            issues.append({'ordinal':ordinal,'reasons':['degenerate_native_curve']});continue
        cuts={}
        for name,point,tangent in [('start',record['sourceSpans'][0][0],record['sourceSpans'][0][:2]),('end',record['sourceSpans'][-1][1],record['sourceSpans'][-1][:2])]:
            work.charge(len(line)-1)
            try:cuts[name]=nearest_projection(point,tangent,line,lengths)['fraction']
            except PilotError:pass
        options=[('full',0.,1.)]
        if 'start' in cuts:options.extend([('start_low',0.,cuts['start']),('start_high',cuts['start'],1.)])
        if 'end' in cuts:options.extend([('end_low',0.,cuts['end']),('end_high',cuts['end'],1.)])
        if len(cuts)==2:options.append(('both',min(cuts.values()),max(cuts.values())))
        for mode,low,high in options:
            if (high-low)*lengths[-1]<=TIE:continue
            try:
                direction,entry,exit_=interval_curve(line,lengths,low,high,box,source,caps);first,last=(low,high) if not direction else (high,low)
                cut_start=mode.startswith('start') or mode=='both';cut_end=mode.startswith('end') or mode=='both'
                if cut_start and abs(first-cuts['start'])*lengths[-1]>TIE:raise GeometryRejected('terminal_start_orientation')
                if cut_end and abs(last-cuts['end'])*lengths[-1]>TIE:raise GeometryRejected('terminal_end_orientation')
                mask=0
                for i in indices:
                    work.charge(len(line)-1)
                    tangent=record['sourceSpans'][samples[i][0]][:2]
                    try:fraction=nearest_projection(points[i],tangent,line,lengths)['fraction']
                    except PilotError:raise GeometryRejected('ambiguous_original_sample_projection') from None
                    if low-TIE/lengths[-1]<=fraction<=high+TIE/lengths[-1]:mask|=1<<i
                key=f'{ordinal}/{mode}'
                nodes[key]={'ordinal':ordinal,'variantKey':key,'mode':mode,'direction':direction,'entryId':None if cut_start else meta['endpointIds'][direction],
                            'exitId':None if cut_end else meta['endpointIds'][1-direction],'entryPoint':point_at(line,lengths,first),'exitPoint':point_at(line,lengths,last),
                            'entryFraction':first,'exitFraction':last,'fractionBasis':'normalized_haversine_native_polyline_length',
                            'entryProgress':[entry,entry],'exitProgress':[exit_,exit_],'progressBasis':'continuous_original_source_geometric_km',
                            'sampleMin':entry,'sampleMax':exit_,'maskHex':hex(mask)}
            except GeometryRejected as error:rejected.append({'mode':mode,'reason':str(error)})
        if rejected:issues.append({'ordinal':ordinal,'variantExclusions':rejected})
    return nodes,issues,work.used,nearby,set(aligned)


def match(record,metadata,lines,index,box,check=lambda:None,caps=CAPS):
    samples,points,_,weights=index.support(record['sourceSpans'],check)
    require(math.isclose(math.fsum(weights),record['sourceKm'],rel_tol=1e-12,abs_tol=1e-9),'Continuous unchanged weighted denominator')
    original_aligned={ordinal for sample in samples for ordinal in sample[4]}
    base={'windowId':record['windowId'],'arc':record['arc'],'sourceClassKph':record['sourceClassKph'],'sourceKm':record['sourceKm'],'sampleCount':len(samples),'sampleMemberships':sum(len(s[4]) for s in samples),'alignedNativeParts':len(original_aligned),
          'sourceAdequacyQualified':False,'carPermissionReviewed':False,'uniquePhysicalMatchQualified':False,'usableLimitOrMatchingQualified':False,'modelChanged':False}
    try:
        nodes,issues,work,nearby,aligned=fragments(metadata,lines,index,record,samples,points,box,check,caps)
    except ProjectionCap:
        return base|{'status':'projection_cap','candidates':[],'alignedPartBindings':[metadata[i] for i in sorted(original_aligned)],'unrepresentedParts':sorted(original_aligned),'fragmentIssues':[],
                     'searchCapped':True,'capReasons':['continuous_projection_or_nearby_part_cap'],'expandedStates':0,'projectionComparisonsBound':caps['projectionComparisons']+1}
    search=search_fragments(nodes,weights,maximum_rows=caps['searchRows'],maximum_states=caps['searchStates'],check=check);groups={}
    for candidate in search['candidates']:
        path=tuple(candidate['rowOrdinals']);key=min(path,path[::-1]);group=groups.setdefault(key,{'nativeParts':list(key),'variants':[],'maximumSupportedKm':0.,
             'allUnscopedNumeric':all(metadata[i]['attributes']['unscopedNumeric'] for i in key),'allSupportedNativeRoles':all(metadata[i]['nativeTags'].get('highway') in ROLES for i in key)})
        group['variants'].append(candidate);group['maximumSupportedKm']=max(group['maximumSupportedKm'],candidate['supportedKm'])
    represented={n['ordinal'] for n in nodes.values()};unrepresented=sorted(aligned-represented);bound=aligned|{i for c in search['candidates'] for i in c['rowOrdinals']}
    status='search_capped' if search['searchCapped'] else 'single_acquired_file_geometric_path' if len(groups)==1 else 'multiple_acquired_file_geometric_paths' if groups else 'no_path_under_fragment_rules'
    return base|{'status':status,'candidates':list(groups.values()),'alignedPartBindings':[metadata[i] for i in sorted(bound)],'unrepresentedParts':unrepresented,'fragmentIssues':issues,
                 'rejectedAlignedGeometryRetained':bool(unrepresented),'candidateUniquenessScope':'Only candidates satisfying the frozen continuous source-corridor/window/progress/terminal rules; rejected alternatives remain visible. No physical/access/source completeness admission.',
                 'nearbyNativeParts':len(nearby),'continuousGeometryVariants':len(nodes),'zeroOriginalSampleVariants':sum(n['maskHex']=='0x0' for n in nodes.values()),'projectionComparisonsBound':work,
                 'searchCapped':search['searchCapped'],'capReasons':search['capReasons'],'expandedStates':search['expandedStates']}


def summary(records):
    from coarse_osm_match_v1 import summary as original_summary
    # Numeric opportunity remains separate from car/role/physical applicability.
    return original_summary(records)
