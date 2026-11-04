"""Exact planar containment diagnostics for bounded publisher polygon metadata."""
from fractions import Fraction
import re

from coarse_timing_input import require


def orientation(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def on_segment(a,b,p):
    return orientation(a,b,p)==0 and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1])


def segments_touch(a,b,c,d):
    ab_c,ab_d=orientation(a,b,c),orientation(a,b,d)
    cd_a,cd_b=orientation(c,d,a),orientation(c,d,b)
    return (ab_c*ab_d<0 and cd_a*cd_b<0) or any((o==0 and on_segment(x,y,p)) for o,x,y,p in [(ab_c,a,b,c),(ab_d,a,b,d),(cd_a,c,d,a),(cd_b,c,d,b)])


def parse_poly(raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=131072,'Publisher polygon byte bound')
    try:lines=raw.decode('ascii').splitlines()
    except UnicodeError:require(False,'Publisher polygon ASCII format')
    require(lines and 0<len(lines[0])<=128,'Publisher polygon name')
    rings=[];position=1;vertices=0;names=set()
    while position<len(lines):
        name=lines[position].strip();position+=1
        if name=='END':
            require(position==len(lines) and rings,'Publisher polygon final END');return rings
        require(name and len(name)<=128 and name not in names and len(rings)<100,'Publisher polygon ring label/count')
        names.add(name);points=[]
        while position<len(lines) and lines[position].strip()!='END':
            words=lines[position].split();position+=1;require(len(words)==2,'Publisher polygon coordinate row')
            require(all(re.fullmatch(r'[+-]?(?:[0-9]{1,10}(?:\.[0-9]{0,16})?|\.[0-9]{1,16})(?:[eE][+-]?[0-9]{1,2})?',word) is not None for word in words),'Publisher polygon bounded numeric grammar')
            try:x,y=map(Fraction,words)
            except (ValueError,ZeroDivisionError):require(False,'Publisher polygon finite numeric coordinate')
            require(-180<=x<=180 and -90<=y<=90 and (not points or points[-1]!=(x,y)),'Publisher polygon coordinate range/duplicate')
            points.append((x,y));vertices+=1;require(vertices<=5000,'Publisher polygon vertex bound')
        require(position<len(lines) and len(points)>=4 and points[0]==points[-1] and len(set(points))>=3,'Publisher polygon closed ring')
        require(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]))!=0,'Publisher polygon nonzero ring area')
        position+=1;rings.append({'hole':name.startswith('!'),'points':points})
    require(False,'Publisher polygon missing final END')


def ring_location(point,points):
    inside=False
    for a,b in zip(points,points[1:]):
        if on_segment(a,b,point):return 'boundary'
        if (a[1]>point[1])!=(b[1]>point[1]):
            cross=orientation(a,b,point)
            if (b[1]>a[1] and cross>0) or (b[1]<a[1] and cross<0):inside=not inside
    return 'inside' if inside else 'outside'


def polygon_location(point,rings):
    locations=[(r['hole'],ring_location(point,r['points'])) for r in rings]
    if any(place=='boundary' for _,place in locations):return 'boundary'
    return 'inside' if any(not hole and place=='inside' for hole,place in locations) and not any(hole and place=='inside' for hole,place in locations) else 'outside'


def review_window(window,rings):
    bbox=window['bbox'];require(len(bbox)==4 and all(type(v) in (int,float) for v in bbox),'Publisher window bbox')
    try:left,bottom,right,top=map(Fraction,bbox)
    except (ValueError,OverflowError,ZeroDivisionError):require(False,'Publisher window finite bbox')
    require(-180<=left<right<=180 and -90<=bottom<top<=90,'Publisher window bounds')
    corners=[(left,bottom),(right,bottom),(right,top),(left,top)];edges=list(zip(corners,corners[1:]+corners[:1]))
    locations=[polygon_location(p,rings) for p in corners]
    boundary_touches=False
    for ring in rings:
        for a,b in zip(ring['points'],ring['points'][1:]):
            if left<=a[0]<=right and bottom<=a[1]<=top or any(segments_touch(a,b,c,d) for c,d in edges):boundary_touches=True;break
        if boundary_touches:break
    return {'id':window['id'],'cornerLocations':locations,'boundaryTouchesWindow':boundary_touches,
            'strictlyInsideReviewedPolygon':all(p=='inside' for p in locations) and not boundary_touches,
            'sourceSnapshotOrRoadCompletenessQualified':False}
