"""Bounded way-only lane overlay over immutable typed country source columns."""
from array import array
from bisect import bisect_left
from collections import Counter

import coarse_osm_car_conditional_speed_v1 as old
import coarse_osm_car_explicit_lanes_v1 as new
from coarse_osm_conditional_overlay_v1 import FieldColumn


def prepare(ids,xy,anchors,geometry,ways,arcs,records,native_costs,check=lambda:None):
    assert 0<len(ids)<=50000000 and len(xy)==2*len(ids)
    assert 0<len(anchors)<=len(ids) and len(ways)<=5000000 and len(geometry)<2**32
    assert len(arcs)<=16000000
    way_ids=FieldColumn(ways,0);arc_ways=FieldColumn(arcs,2)
    changed_ways={};added=[];counts=Counter();previous=0
    def exact(values,value):
        at=bisect_left(values,value);return at if at<len(values) and values[at]==value else None
    for record in records:
        check();identity=record['id'];assert record['type']=='way' and identity>previous;previous=identity
        counts['records']+=1;assert counts['records']<=250000
        tags=record['tags'];before,after=old.way_policy(tags),new.way_policy(tags)
        assert before.reason=='lane-access' and after.reason is None
        i=exact(way_ids,identity);assert i is not None and ways[i][1:3]==(0.,0.)
        pos=bisect_left(arc_ways,i);assert pos==len(arcs) or arc_ways[pos]!=i,'Old lane exclusion has no existing preclosure arc'
        row=ways[i];assert row[3]>>8==6 and row[3]&15==0,'Only original lane exclusions can reopen'
        role=(row[3]>>4)&15;assert old.POLICY['roles'][role]==tags['highway']
        directions=int(after.forward is not None)|(int(after.backward is not None)<<1)
        defaults=int(after.forward_default)|(int(after.backward_default)<<1)
        changed_ways[i]=(identity,after.forward or 0.,after.backward or 0.,directions|(defaults<<2)|(role<<4),row[4])
        start=0 if i==0 else ways[i-1][4];end=row[4]
        assert 2<=end-start<=2000000 and end<=len(geometry)
        chain=array('I',(geometry[p] for p in range(start,end)));cuts=[]
        for j,node in enumerate(chain):
            assert 0<=node<len(ids)
            anchor=exact(anchors,node)
            if anchor is not None:cuts.append((j,anchor))
        assert cuts[0][0]==0 and cuts[-1][0]==len(chain)-1
        coordinates=array('i');same=bytearray()
        for left,right in zip(chain,chain[1:]):
            coordinates.extend((xy[2*left],xy[2*left+1],xy[2*right],xy[2*right+1]));same.append(int(left==right))
        prices={direction:native_costs.costs(coordinates,array('d',[speed])*len(same),same)
                for direction,speed in ((1,after.forward),(-1,after.backward)) if speed is not None}
        for (first,tail),(last,head) in zip(cuts,cuts[1:]):
            if all(same[first:last]):continue
            for direction in (1,-1):
                if direction not in prices:continue
                ms,ticks=native_costs.sum(prices[direction][first:last]);assert ms>0 and ticks==(ms+124)//125
                added.append((tail if direction==1 else head,head if direction==1 else tail,i,first,last,direction,ms))
                assert len(added)<=1000000
        counts['changedGraphWays']+=1;counts['newPreClosureArcs']=len(added)
    assert len(changed_ways)==counts['changedGraphWays']
    return {'wayRows':changed_ways,'nodeFlags':{},'arcs':added,'counts':dict(counts)}
