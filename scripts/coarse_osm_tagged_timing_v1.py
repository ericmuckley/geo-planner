"""Derived travel-time costs; original legal-speed source facts stay read-only."""
from array import array
import math

MAX_MS=(2**32-1)*125
MAX_PRIMITIVES=2000000
MAX_BATCH_ARCS=65536
POLICY={'id':'explicit-speed-static-estimate-90-v1','taggedSpeedRatio':[9,10],'defaultSpeedRatio':[1,1],
        'scope':'Estimated driving speeds only;no access/direction/closure/node/turn/geometry change. Original legal-speed facts retained separately. No hosted settings or observed speed claim.'}


def estimated_way(row):
    identity,forward,backward,flags,end=row
    assert type(identity) is int and 0<identity<2**63 and type(flags) is int and 0<=flags<2**32 and type(end) is int and 0<=end<2**32
    speeds=[]
    for index,speed in enumerate((forward,backward)):
        assert type(speed) in (int,float) and math.isfinite(speed) and 0<=speed<=160
        assert bool(flags&(1<<index))==(speed>0)
        speeds.append(speed if speed==0 or flags&(1<<(index+2)) else speed*0.9)
    return identity,*speeds,flags,end


def reprice_arcs(ways,geometry,xy,anchors,arcs,kernel,stats,check=lambda:None,*,primitive_limit=MAX_PRIMITIVES,arc_limit=MAX_BATCH_ARCS):
    assert 0<primitive_limit<=MAX_PRIMITIVES and 0<arc_limit<=MAX_BATCH_ARCS
    assert len(xy)%2==0 and 0<len(anchors)<=len(xy)//2 and 0<len(ways)<=5000000 and len(arcs)<=16000000
    coords=array('i');old_speeds=array('d');new_speeds=array('d');same=bytearray();batch=[];previous=None
    stats.update(arcsChecked=0,costsChanged=0,defaultArcsChecked=0,primitiveOccurrences=0,nativeBatches=0)
    def flush():
        if not batch:return []
        check();old=kernel.costs(coords,old_speeds,same);new=kernel.costs(coords,new_speeds,same)
        assert len(old)==len(new)==len(same)
        output=[]
        for arc,start,end,default in batch:
            before=sum(old[start:end]);after=sum(new[start:end])
            assert before==arc[6] and 0<before<=after<=MAX_MS,'Exact original source price and nondecreasing proposed cost'
            if default:assert before==after,'Assumed/default speed unchanged'
            output.append((*arc[:6],after));stats['arcsChecked']+=1;stats['costsChanged']+=after!=before;stats['defaultArcsChecked']+=default
        stats['primitiveOccurrences']+=len(same);stats['nativeBatches']+=1
        del coords[:];del old_speeds[:];del new_speeds[:];same.clear();batch.clear()
        return output
    check()
    for ordinal in range(len(arcs)):
        if ordinal%4096==0:check()
        arc=arcs[ordinal];assert len(arc)==7
        tail,head,way,first,last,direction,ms=arc
        assert all(type(v) is int for v in arc) and 0<=way<len(ways) and 0<=tail<len(anchors) and 0<=head<len(anchors)
        assert direction in (-1,1) and 0<ms<=MAX_MS
        key=(way,first,last,-direction);assert previous is None or previous<key;previous=key
        row=ways[way];proposed=estimated_way(row);start=0 if way==0 else ways[way-1][4]
        assert 0<=start<=row[4]<=len(geometry) and 0<=first<last<row[4]-start
        a,b=geometry[start+first],geometry[start+last]
        assert anchors[tail]==(a if direction==1 else b) and anchors[head]==(b if direction==1 else a)
        speed_index=1 if direction==1 else 2;speed=row[speed_index];estimate=proposed[speed_index];assert speed>0
        default=bool(row[3]&(1<<(speed_index+1)))
        count=last-first;assert count<=primitive_limit
        if len(same)+count>primitive_limit or len(batch)>=arc_limit:
            yield from flush()
        offset=len(same)
        for position in range(first,last):
            left,right=geometry[start+position],geometry[start+position+1]
            assert 0<=left<len(xy)//2 and 0<=right<len(xy)//2
            coords.extend((xy[2*left],xy[2*left+1],xy[2*right],xy[2*right+1]));same.append(int(left==right));old_speeds.append(speed);new_speeds.append(estimate)
        batch.append((arc,offset,len(same),default))
    yield from flush()
    assert stats['arcsChecked']==len(arcs)
    check()
