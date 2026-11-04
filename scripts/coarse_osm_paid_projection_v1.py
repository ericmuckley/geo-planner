"""Independent local spherical-basis projection, stable for E7-sized segments."""
import math

R=6371008.8
RAD=math.pi/180


def longitude_delta(a,b):
    value=b[0]-a[0]
    if value>1800000000:value-=3600000000
    if value<-1800000000:value+=3600000000
    return value/1e7*RAD


def angle(a,b):
    dy=math.sin((b[1]-a[1])/1e7*RAD/2);dx=math.sin(longitude_delta(a,b)/2)
    return 2*math.asin(min(1,math.sqrt(dy*dy+math.cos(a[1]/1e7*RAD)*math.cos(b[1]/1e7*RAD)*dx*dx)))


def basis_components(a,p):
    dl=longitude_delta(a,p);lat_a=a[1]/1e7*RAD;lat_p=p[1]/1e7*RAD
    east=math.sin(dl)*math.cos(lat_p)
    north=math.sin((p[1]-a[1])/1e7*RAD)+2*math.sin(lat_a)*math.cos(lat_p)*math.sin(dl/2)**2
    dy=math.sin((p[1]-a[1])/1e7*RAD/2);dx=math.sin(dl/2)
    along_origin=1-2*(dy*dy+math.cos(lat_a)*math.cos(lat_p)*dx*dx)
    return east,north,along_origin


def frame(a,b):
    length=angle(a,b);east,north,_=basis_components(a,b);norm=math.hypot(east,north)
    return a,b,length,(east/norm if norm else 0),(north/norm if norm else 1)


def project(p,segment):
    a,b,length,sin_heading,cos_heading=segment
    if length<1e-12 or length>math.pi-1e-12:
        da,db=angle(a,p),angle(b,p)
        return (R*da,0.) if da<=db else (R*db,1.)
    east,north,origin_dot=basis_components(a,p)
    along=math.atan2(east*sin_heading+north*cos_heading,origin_dot)
    if along<=0:return R*angle(a,p),0.
    if along>=length:return R*angle(b,p),1.
    across=east*cos_heading-north*sin_heading
    return R*math.asin(min(1,abs(across))),along/length
