"""Independent cached-source/span/index/BFS audit of the protected geometry preflight."""
import argparse
from array import array
from bisect import bisect_left
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

from coarse_census import ROOT, load_tool, part_key, road_parts
from coarse_path_features import distance_km


def sha(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1048576):result.update(block)
    return result.hexdigest()


def axis(value):
    result=math.floor(value*40)
    while result/40>value:result-=1
    while (result+1)/40<=value:result+=1
    return result


def square(point):
    return axis(point[0]),axis(point[1])


def sequence(points):
    result=[]
    def add(key):
        if not result or result[-1]!=key:result.append(key)
    add(square(points[0]))
    for a,b in zip(points,points[1:]):
        add(square([(a[0]+b[0])/2,(a[1]+b[1])/2]));add(square(b))
    return result


def source_points(raw):
    clean=[raw[0]]
    for point in raw[1:]:
        if point!=clean[-1]:clean.append(point)
    output=[list(clean[0])];cuts=[False];lengths=[]
    for a,b in zip(clean,clean[1:]):
        intersections={}
        for k in [0,1]:
            low,high=sorted([a[k],b[k]])
            index=math.ceil(low*40)-1
            while index/40<high:
                boundary=index/40
                if low<boundary<high:
                    t=(Fraction(boundary)-Fraction(a[k]))/(Fraction(b[k])-Fraction(a[k]))
                    intersections.setdefault(t,{})[k]=boundary
                index+=1
        last_t=Fraction(0)
        for t,boundaries in sorted(intersections.items())+[(Fraction(1),{})]:
            point=[float(Fraction(a[k])+t*(Fraction(b[k])-Fraction(a[k]))) for k in [0,1]] if t!=1 else list(b)
            for k,value in boundaries.items():point[k]=value
            length=distance_km(output[-1],point)
            lengths.append(length if length else distance_km(a,b)*float(t-last_t))
            output.append(point);cuts.append(t!=1);last_t=t
    owners=[square([(a[0]+b[0])/2,(a[1]+b[1])/2]) for a,b in zip(output,output[1:])]
    protected=[0]+[i for i in range(1,len(output)-1) if cuts[i] or owners[i-1]!=owners[i] or square(output[i])!=owners[i-1]]+[len(output)-1]
    return output,lengths,owners,protected


def integers(raw,expected):
    values=[];number=shift=0
    for byte in raw:
        assert shift<35
        number|=(byte&127)<<shift
        if byte&128:shift+=7;continue
        assert number<=0xffffffff
        values.append((number>>1)^-(number&1));number=shift=0
    assert shift==0 and len(values)==expected
    return values


def read_arrays(report):
    arrays={}
    for name,record in report['packedArrays'].items():
        path=ROOT/record['path'];assert sha(path)==record['sha256']
        with gzip.open(path,'rb') as stream:raw=stream.read()
        assert hashlib.sha256(raw).hexdigest()==record['rawSha256']
        values=array(record['typecode']);values.frombytes(raw)
        if sys.byteorder!='little':values.byteswap()
        assert len(values)==record['elements'] and len(raw)==record['rawBytes']
        assert record['base64Bytes']==4*((path.stat().st_size+2)//3)
        arrays[name]=values
    return arrays


def run(directory):
    started=time.perf_counter()
    report=json.loads((directory/'report.json').read_text())
    plan_path=ROOT/'docs/evidence/coarse-backbone-geometry-2026-10-25/plan.json'
    assert sha(plan_path)==report['planSha256']=='fb1f8cad561e791c55db31751e5b0897e3ba7de1ceca4c11bcb978226f2d2420'
    plan=json.loads(plan_path.read_text())
    for name,expected in plan['inputs'].items():assert sha(ROOT/name)==expected,name
    for name,expected in report['proofs'].items():assert sha(ROOT/name)==expected,name
    data=read_arrays(report)
    old=json.loads((ROOT/'docs/evidence/coarse-backbone-preflight-2026-10-25/report.json').read_text())
    previous={}
    for name in ['nodeCoordinates','arcFrom','arcTo','arcRoadKm','arcDeciseconds','arcSpeedKph']:
        record=old['packedArrays'][name]
        with gzip.open(ROOT/record['path'],'rb') as stream:raw=stream.read()
        values=array(record['typecode']);values.frombytes(raw)
        if sys.byteorder!='little':values.byteswap()
        previous[name]=values
    original=len(previous['nodeCoordinates'])//2
    assert data['nodeCoordinates'][:original*2]==previous['nodeCoordinates']
    nodes={tuple(previous['nodeCoordinates'][i:i+2]):i//2 for i in range(0,original*2,2)}
    n,m=report['nodes'],report['arcs']
    assert len(data['arcFrom'])==len(data['arcTo'])==len(data['arcRoadKm'])==len(data['arcMinutes'])==m
    assert len(data['nodeCoordinates'])==n*2
    assert len(data['arcByteOffsets'])==len(data['arcInteriorOffsets'])==m+1
    assert data['arcByteOffsets'][0]==data['arcInteriorOffsets'][0]==0
    assert data['arcByteOffsets'][-1]==len(data['geometryBytes'])
    assert data['arcInteriorOffsets'][-1]==len(data['interiorSourceKm'])
    assert len(data['crossingFirstArc'])==n-original
    for i,arc in enumerate(data['crossingFirstArc']):
        node=original+i
        assert data['arcTo'][arc]==node and data['arcFrom'][arc+1]==node
    assert len(data['endpointAdjOffsets'])==original+1
    assert data['endpointAdjOffsets'][0]==0 and data['endpointAdjOffsets'][-1]==len(data['endpointAdjArcs'])
    assert len(data['cellArcOffsets'])==len(data['cellIds'])+1
    assert data['cellArcOffsets'][0]==0 and data['cellArcOffsets'][-1]==len(data['cellArcs'])
    for i,key in enumerate(data['cellIds']):
        assert i==0 or key>data['cellIds'][i-1]
        lo,hi=data['cellArcOffsets'][i:i+2]
        assert all(lo==j or data['cellArcs'][j-1]<data['cellArcs'][j] for j in range(lo,hi))
    manifest=json.loads((ROOT/'data/coarse-sources/tiger-2026/national-v1/sources.json').read_text())
    sources=sorted(manifest['sources'],key=lambda row:row['sha256'])
    shapefile,_=load_tool('docs/evidence/coarse-source-2026-10-22/tool.json')
    seen=set();part_count=parent_count=arc_count=raw_parts=duplicates=vertices=0
    next_node=original;max_error=max_chord=max_length_error=max_time_error=0.
    expected_cell_entries=expected_endpoint_entries=0
    with gzip.open(directory/'parents.jsonl.gz','rt') as parents,gzip.open(directory/'parts.jsonl.gz','rt') as parts:
        for partition,source in enumerate(sources):
            for part in road_parts(source,shapefile):
                raw_parts+=1;identity=part_key(part)
                if identity in seen:duplicates+=1;continue
                seen.add(identity)
                metadata=json.loads(next(parts));assert metadata['part']==part_count
                assert metadata['geometrySha256']==identity.hex() and metadata['sourceSha256']==source['sha256']
                assert metadata['id']==part['id'] and metadata['multipartIndex']==part['part'] and metadata['class']==part['class']
                points=part['points'];vertices+=len(points);assert metadata['vertices']==len(points)
                cumulative=[0.]
                for a,b in zip(points,points[1:]):cumulative.append(cumulative[-1]+distance_km(a,b))
                junctions=[i for i,point in enumerate(points) if tuple(point) in nodes]
                assert junctions[0]==0 and junctions[-1]==len(points)-1
                assert metadata['firstParent']==parent_count and data['partArcOffsets'][part_count]==arc_count
                for start,end in zip(junctions,junctions[1:]):
                    km=cumulative[end]-cumulative[start]
                    if km==0:continue
                    frame=json.loads(next(parents));assert frame['parent']==parent_count and frame['part']==part_count
                    assert frame['start']==start and frame['end']==end and frame['firstArc']==arc_count
                    a,b=nodes[tuple(points[start])],nodes[tuple(points[end])]
                    speed=plan['sources']['speeds'][part['class']];cost=max(1,math.ceil(km/speed*36000))
                    assert previous['arcFrom'][parent_count]==a and previous['arcTo'][parent_count]==b
                    assert previous['arcRoadKm'][parent_count]==km and previous['arcDeciseconds'][parent_count]==cost
                    full,lengths,owners,protected=source_points(points[start:end+1])
                    assert protected==frame['protected'] and len(frame['spans'])==len(protected)-1
                    expected_nodes=[a]+list(range(next_node,next_node+len(protected)-2))+[b]
                    next_node+=len(protected)-2
                    factor=km/math.fsum(lengths);result=[];parent_km=parent_time=0.
                    for first,last,x,y,span in zip(protected,protected[1:],expected_nodes,expected_nodes[1:],frame['spans']):
                        assert span['first']==first and span['last']==last
                        kept=span['kept'];assert kept[0]==first and kept[-1]==last and kept==sorted(set(kept))
                        assert all(first<=index<=last for index in kept)
                        arc=arc_count;arc_count+=1
                        assert data['arcFrom'][arc]==x and data['arcTo'][arc]==y
                        assert list(data['nodeCoordinates'][x*2:x*2+2])==full[first]
                        assert list(data['nodeCoordinates'][y*2:y*2+2])==full[last]
                        expected_km=math.fsum(lengths[first:last])*factor
                        expected_time=cost/600*(expected_km/km)
                        assert math.isclose(data['arcRoadKm'][arc],expected_km,rel_tol=1e-12,abs_tol=1e-12)
                        assert math.isclose(data['arcMinutes'][arc],expected_time,rel_tol=1e-12,abs_tol=1e-12)
                        assert data['arcRoadKm'][arc]>0 and data['arcMinutes'][arc]>0 and data['arcSpeedKph'][arc]==speed
                        parent_km+=data['arcRoadKm'][arc];parent_time+=data['arcMinutes'][arc]
                        max_chord=max(max_chord,(distance_km(full[first],full[last])-data['arcMinutes'][arc]/60*speed)*1000)
                        byte_lo,byte_hi=data['arcByteOffsets'][arc:arc+2]
                        lo,hi=data['arcInteriorOffsets'][arc:arc+2];assert hi-lo==len(kept)-2
                        encoded=integers(data['geometryBytes'][byte_lo:byte_hi],2*(hi-lo))
                        q=[round(v*100000) for v in full[first]];decoded=[full[first]]
                        for j,index in enumerate(kept[1:-1]):
                            q=[q[k]+encoded[j*2+k] for k in [0,1]]
                            decoded.append([v/100000 for v in q])
                            expected_distance=math.fsum(lengths[first:index])*factor
                            assert math.isclose(data['interiorSourceKm'][lo+j],expected_distance,rel_tol=1e-10,abs_tol=1e-10)
                            assert square(decoded[-1])==owners[first]
                        decoded.append(full[last])
                        for j,(left,right) in enumerate(zip(kept,kept[1:])):
                            ax,ay=decoded[j];bx,by=decoded[j+1];dx,dy=bx-ax,by-ay;norm=dx*dx+dy*dy
                            for index in range(left,right+1):
                                px,py=full[index]
                                t=0 if norm==0 else max(0,min(1,((px-ax)*dx+(py-ay)*dy)/norm))
                                error=math.hypot(px-ax-t*dx,py-ay-t*dy)*111320
                                max_error=max(max_error,error)
                                assert error<=25+1e-9
                        for key in sequence(decoded):
                            if not result or result[-1]!=key:result.append(key)
                        expected_cells={owners[first],square(full[first]),square(full[last])}
                        for cx,cy in expected_cells:
                            cell_id=(cy-960)*2360+(cx+5000)
                            position=bisect_left(data['cellIds'],cell_id)
                            assert position<len(data['cellIds']) and data['cellIds'][position]==cell_id
                            low,high=data['cellArcOffsets'][position:position+2]
                            hit=bisect_left(data['cellArcs'],arc,low,high)
                            assert hit<high and data['cellArcs'][hit]==arc
                        expected_cell_entries+=len(expected_cells)
                        for node in [x,y]:
                            if node<original:
                                low,high=data['endpointAdjOffsets'][node:node+2]
                                hit=bisect_left(data['endpointAdjArcs'],arc,low,high)
                                assert hit<high and data['endpointAdjArcs'][hit]==arc
                                expected_endpoint_entries+=1
                    assert result==sequence(full)==[tuple(key) for key in frame['sourceCells']]==[tuple(key) for key in frame['resultCells']]
                    assert frame['lastArc']==arc_count
                    max_length_error=max(max_length_error,abs(parent_km-km));max_time_error=max(max_time_error,abs(parent_time-cost/600))
                    parent_count+=1
                assert metadata['lastParent']==parent_count
                part_count+=1;assert data['partArcOffsets'][part_count]==arc_count
            assert time.perf_counter()-started<=600,'Audit time guard'
            print(f"Independent source {partition+1}/49; parents={parent_count}",file=sys.stderr,flush=True)
        assert parents.read()=='' and parts.read()==''
    assert next_node==n and arc_count==m and parent_count==501493 and part_count==223392
    assert raw_parts==261862 and duplicates==38470 and vertices==24450400
    assert expected_cell_entries==len(data['cellArcs']) and expected_endpoint_entries==len(data['endpointAdjArcs'])
    assert max_chord<=.001 and max_time_error<=1e-8
    # Independently recover all connected components with adjacency/BFS.
    degree=array('I',[0])*n
    for a,b in zip(data['arcFrom'],data['arcTo']):degree[a]+=1;degree[b]+=1
    offsets=array('I',[0])
    for value in degree:offsets.append(offsets[-1]+value)
    neighbors=array('I',[0])*(2*m);cursor=offsets[:-1]
    for a,b in zip(data['arcFrom'],data['arcTo']):
        neighbors[cursor[a]]=b;cursor[a]+=1;neighbors[cursor[b]]=a;cursor[b]+=1
    component=array('i',[-1])*n;components=0
    for node in range(n):
        if component[node]>=0:continue
        stack=[node];component[node]=components
        while stack:
            a=stack.pop()
            for i in range(offsets[a],offsets[a+1]):
                b=neighbors[i]
                if component[b]<0:component[b]=components;stack.append(b)
        components+=1
    lengths=[0.]*components
    for node,length in zip(data['arcFrom'],data['arcRoadKm']):lengths[component[node]]+=length
    share=max(lengths)/sum(lengths)
    assert components==3100 and abs(share-.9854365119558087)<1e-10
    new_bytes=sum(len(name)+2+1+2+5+info['base64Bytes']+1 for name,info in report['packedArrays'].items())+1024
    forecast=report['storageForecast']
    assert new_bytes==forecast['newPackedJsonBytesIncludingMetadata']
    assert forecast['projectedFunctionBytes']==forecast['keptV9JsonBytes']+new_bytes+3822197+4194304
    assert not report['gates']['projectedFunction'] and not report['geometryAndSizePassed']
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
    assert rss<=1073741824
    return {'sourceParts':raw_parts,'uniqueParts':part_count,'originalVertices':vertices,
            'parents':parent_count,'nodes':n,'arcs':m,'allOriginalCostsAndProtectedPositions':True,
            'allSourceSpansAndCellRosters':True,'allSparseAdjacencyAndCellIndexMemberships':True,
            'maximumDeviationMeters':max_error,'maximumChordUnderchargeMeters':max_chord,
            'maximumParentMinutesError':max_time_error,'independentBfsComponents':components,
            'largestRoadLengthFraction':share,'projectedFunctionBytes':forecast['projectedFunctionBytes'],
            'storageFailureConfirmed':True,'providerRequests':0,'wallSeconds':time.perf_counter()-started,
            'auditorMaxRssBytes':rss,'scope':'Independent full cached-source span/protected-position/cost/decoded-geometry/index/BFS verification. No source producer, simplifier, route search, runtime change, service/key/env/DB access or accuracy/cloud runtime claim.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.directory),indent=2))
