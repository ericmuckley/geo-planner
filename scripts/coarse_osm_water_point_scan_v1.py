"""Exact query-point classification against accepted saved planar water geometry.

Outside these polygons is absence of accepted water evidence, not proof of land.
"""
from array import array
from bisect import bisect_left,bisect_right
from fractions import Fraction
import math

from assemble_osm_water_polygons_v1 import FEATURE,RING,POINT
from coarse_osm_water_reference_store_v1 import Reader
from coarse_timing_input import require


def query(coordinate):
    require(isinstance(coordinate,(list,tuple)) and len(coordinate)==2,'Water point longitude/latitude pair')
    values=[]
    for value,limit in zip(coordinate,(180,90)):
        require(type(value) in (int,float,str) and len(str(value))<=40,'Water point coordinate type/size')
        number=Fraction(str(value));require(abs(number)<=limit,'Water point coordinate range');values.append(number*10000000)
    scale=math.lcm(values[0].denominator,values[1].denominator)
    require(scale<=10**24,'Water point exact decimal precision cap')
    return (int(values[0]*scale),int(values[1]*scale),scale,float(values[0]),float(values[1]))


def location(point,vertices):
    """Return outside=-1, boundary=0, inside=1 using exact integer winding."""
    px,py,scale,_,_=point;winding=0
    for index in range(0,len(vertices)-2,2):
        ax,ay,bx,by=vertices[index],vertices[index+1],vertices[index+2],vertices[index+3]
        cross=(bx-ax)*(py-ay*scale)-(by-ay)*(px-ax*scale)
        if cross==0 and min(ax,bx)*scale<=px<=max(ax,bx)*scale and min(ay,by)*scale<=py<=max(ay,by)*scale:return 0
        if ay*scale<=py<by*scale and cross>0:winding+=1
        if by*scale<=py<ay*scale and cross<0:winding-=1
    return 1 if winding else -1


def scan(root,report,coordinates,check=lambda:None):
    require(isinstance(coordinates,list) and 0<len(coordinates)<=512,'Water point bounded arbitrary query list')
    points=[query(c) for c in coordinates];by_x=sorted((p[3],i) for i,p in enumerate(points));xs=[x for x,_ in by_x]
    matches=[{'insideAcceptedWaterFeatures':[],'onAcceptedWaterBoundaries':[]} for _ in points]
    features=rings=nodes=0;last_kind=last_identity=0
    with Reader(root,report) as reader:
        while raw:=reader.read(FEATURE.size):
            check();require(len(raw)==FEATURE.size,'Water point complete feature header')
            kind,identity,count=FEATURE.unpack(raw)
            require(kind in (1,2) and kind>=last_kind and identity>0 and 0<count<=100000,'Water point feature fields/order')
            if kind==last_kind:require(identity>last_identity,'Water point source feature identity order')
            last_kind,last_identity=kind,identity;features+=1;roles=[];groups={};boundaries=set();object_nodes=0
            for rank in range(count):
                raw=reader.read(RING.size);require(len(raw)==RING.size,'Water point complete ring header')
                role,parent,size=RING.unpack(raw)
                require(role in (0,1) and 4<=size<=2000000 and ((role==0 and parent==rank) or (role==1 and 0<=parent<rank and roles[parent]==0)),'Water point source ring fields/parent')
                vertices=array('i');minimum_x=minimum_y=2**31;maximum_x=maximum_y=-2**31;remaining=size;first=last=None
                while remaining:
                    amount=min(remaining,65536);raw=reader.read(amount*16);require(len(raw)==amount*16,'Water point complete native coordinate rows')
                    for native,x,y in POINT.iter_unpack(raw):
                        require(0<native<2**63 and -1800000000<=x<=1800000000 and -900000000<=y<=900000000,'Water point saved source coordinate domain')
                        vertices.extend((x,y));minimum_x=min(minimum_x,x);maximum_x=max(maximum_x,x);minimum_y=min(minimum_y,y);maximum_y=max(maximum_y,y)
                        if first is None:first=(native,x,y)
                        last=(native,x,y)
                    remaining-=amount
                require(first==last and vertices.itemsize==4,'Water point exact native-ID/coordinate closure/platform')
                # A one-E7-unit box margin makes the float index conservative;
                # the actual inclusion/boundary decision uses exact rationals.
                for _,index in by_x[bisect_left(xs,minimum_x-1):bisect_right(xs,maximum_x+1)]:
                    point=points[index]
                    if point[4]<minimum_y-1 or point[4]>maximum_y+1:continue
                    state=location(point,vertices)
                    if state==0:
                        boundaries.add(index)
                        if role==1:groups.setdefault(index,set()).discard(parent)
                    elif state==1:
                        if role==0:groups.setdefault(index,set()).add(rank)
                        else:groups.setdefault(index,set()).discard(parent)
                roles.append(role);rings+=1;nodes+=size;object_nodes+=size
            require(object_nodes<=2000000,'Water point per-feature geometry capacity')
            feature={'kind':kind,'id':identity}
            for index,outers in groups.items():
                if outers:
                    matches[index]['insideAcceptedWaterFeatures'].append(feature)
                    require(len(matches[index]['insideAcceptedWaterFeatures'])<=10000,'Water point explicit water overlap-output bound')
            for index in boundaries:
                matches[index]['onAcceptedWaterBoundaries'].append(feature)
                require(len(matches[index]['onAcceptedWaterBoundaries'])<=10000,'Water point explicit boundary overlap-output bound')
        require(reader.finished,'Water point complete saved geometry EOF')
    for coordinate,result in zip(coordinates,matches):
        result['coordinate']=coordinate
        result['classification']='inside_accepted_water' if result['insideAcceptedWaterFeatures'] else 'on_accepted_water_boundary' if result['onAcceptedWaterBoundaries'] else 'not_in_accepted_water_geometry'
    return {'queries':matches,'allAcceptedFeaturesScanned':features,'allAcceptedRingsScanned':rings,'allAcceptedCoordinateOccurrencesScanned':nodes,
            'scope':'Exact rational points against accepted planar E7 source polygons, preserving holes/islands and overlaps. No geographic completeness or land/shore accuracy proof, permission, snapping, mask/routing/ETA/app change.'}
