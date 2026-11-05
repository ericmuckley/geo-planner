"""Independent raw polygon center/closed-cell checks for compact observations."""
from array import array
from bisect import bisect_left,bisect_right
from fractions import Fraction

from assemble_osm_water_polygons_v1 import FEATURE,RING,POINT
from coarse_osm_water_point_scan_v1 import scan
from coarse_osm_water_reference_store_v1 import Reader
from coarse_timing_input import require


def segment_touches_box(a,b,box):
    """Closed segment/rectangle slab clipping, independent of raster row spans."""
    if max(a[0],b[0])<box[0] or min(a[0],b[0])>box[2] or max(a[1],b[1])<box[1] or min(a[1],b[1])>box[3]:return False
    enter=Fraction(0);leave=Fraction(1)
    for axis in (0,1):
        delta=b[axis]-a[axis]
        if not delta:
            if not box[axis]<=a[axis]<=box[axis+2]:return False
        else:
            low=Fraction(box[axis]-a[axis],delta);high=Fraction(box[axis+2]-a[axis],delta)
            if low>high:low,high=high,low
            enter=max(enter,low);leave=min(leave,high)
            if enter>leave:return False
    return True


def source_boundary_hits(root,report,boxes,check):
    hits=[False]*len(boxes);centers=sorted(((box[0]+box[2])//2,i) for i,box in enumerate(boxes));xs=[x for x,_ in centers]
    half=(boxes[0][2]-boxes[0][0]+1)//2;features=rings=points=0
    with Reader(root,report) as reader:
        while raw:=reader.read(FEATURE.size):
            check();require(len(raw)==FEATURE.size,'Water cell source feature header');kind,identity,count=FEATURE.unpack(raw)
            require(kind in (1,2) and identity>0 and 0<count<=100000,'Water cell source feature fields');features+=1
            roles=[];object_points=0
            for rank in range(count):
                raw=reader.read(RING.size);require(len(raw)==RING.size,'Water cell source ring header');role,parent,size=RING.unpack(raw)
                require(role in (0,1) and 4<=size<=2000000 and ((role==0 and parent==rank) or (role==1 and 0<=parent<rank and roles[parent]==0)),'Water cell source ring/parent fields')
                xy=array('i');low_x=low_y=2**31;high_x=high_y=-2**31;remaining=size;first=last=None
                while remaining:
                    amount=min(remaining,65536);raw=reader.read(amount*16);require(len(raw)==amount*16,'Water cell every native/E7 source row')
                    for native,x,y in POINT.iter_unpack(raw):
                        require(0<native<2**63 and -1800000000<=x<=1800000000 and -900000000<=y<=900000000,'Water cell source coordinate fields')
                        xy.extend((x,y));low_x=min(low_x,x);low_y=min(low_y,y);high_x=max(high_x,x);high_y=max(high_y,y)
                        if first is None:first=(native,x,y)
                        last=(native,x,y)
                    remaining-=amount
                require(first==last,'Water cell exact native/coordinate closure')
                for _,index in centers[bisect_left(xs,low_x-half):bisect_right(xs,high_x+half)]:
                    box=boxes[index]
                    if hits[index] or box[1]>high_y or box[3]<low_y:continue
                    for cursor in range(0,len(xy)-2,2):
                        if segment_touches_box((xy[cursor],xy[cursor+1]),(xy[cursor+2],xy[cursor+3]),box):hits[index]=True;break
                rings+=1;points+=size;object_points+=size;roles.append(role)
            require(object_points<=2000000,'Water cell source object capacity')
        require(reader.finished,'Water cell source complete EOF')
    return hits,(features,rings,points)


def compare(root,polygon_report,exclusion_report,grid,observations,check=lambda:None):
    require(0<len(observations)<=512 and len(grid)==5,'Water cell bounded comparison population/grid')
    x,y,step,width,height=grid;boxes=[];coordinates=[]
    for row in observations:
        require(row['kind']=='cell' and type(row['column']) is int and type(row['row']) is int and 0<=row['column']<width and 0<=row['row']<height,'Water cell supported observation')
        coordinate=row['coordinate'];px=Fraction(str(coordinate[0]))*10000000;py=Fraction(str(coordinate[1]))*10000000
        require((px-x)//step==row['column'] and (py-y)//step==row['row'],'Water cell independent exact decimal index')
        left=x+row['column']*step;bottom=y+row['row']*step
        require(px==Fraction(2*left+step,2) and py==Fraction(2*bottom+step,2),'Water cell comparison uses exact centers')
        boxes.append((left,bottom,left+step,bottom+step));coordinates.append(coordinate)
    polygon=polygon_report['polygons'];expected=(polygon['acceptedFeatures'],polygon['acceptedRings'],polygon['sourcePointsIndependentlyReplayed'])
    membership=scan(root,polygon['geometryStore'],coordinates,check)
    require((membership['allAcceptedFeaturesScanned'],membership['allAcceptedRingsScanned'],membership['allAcceptedCoordinateOccurrencesScanned'])==expected,'Water cell all raw center geometry scanned')
    boundary,counts=source_boundary_hits(root,polygon['geometryStore'],boxes,check);require(counts==expected,'Water cell all raw boundary geometry scanned')
    output=[];mismatches=[]
    for index,(row,box,center) in enumerate(zip(observations,boxes,membership['queries'])):
        excluded=[]
        for feature in exclusion_report['exclusions']['excludedFeatures']:
            bounds=feature['knownSourceBoundsE7']
            if bounds and bounds[0]<=box[2] and bounds[2]>=box[0] and bounds[1]<=box[3] and bounds[3]>=box[1]:excluded.append([feature['kind'],feature['id']])
        water=center['classification']!='not_in_accepted_water_geometry';uncertain=boundary[index] or bool(excluded)
        result={'phase':row['phase'],'sourceIndex':row['sourceIndex'],'coordinate':row['coordinate'],'column':row['column'],'row':row['row'],
                'packetWaterAtCenter':row['waterAtCenter'],'rawSourceCenterClassification':center['classification'],'packetUncertainty':row['sourceUncertainty'],
                'rawSourceBoundaryTouchesCell':boundary[index],'knownExcludedBoundsTouchingCell':excluded,
                'waterMatches':row['waterAtCenter']==water,'uncertaintyMatches':row['sourceUncertainty']==uncertain}
        output.append(result)
        if not result['waterMatches'] or not result['uncertaintyMatches']:mismatches.append(index)
    return {'comparisons':output,'mismatchIndices':mismatches,'allRawCenterCounts':expected,'allRawBoundaryCounts':counts,
            'unboundedSourceFeaturesRetained':exclusion_report['exclusions']['unboundedOrSourceIncompleteFeatures'],
            'scope':'Independent exact decimal indexing/raw polygon winding and closed segment/rectangle clipping for fixed observed cells;512 development checks are not all-cell/national accuracy proof. Global missing geometry stays unqualified; no land/mask/connector/routing/app admission.'}
