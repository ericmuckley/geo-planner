"""Bounded changed-way/source-node facts; full country buffers stay typed.

This prepares an overlay only. The caller owns immutable source authentication,
complete relation input, output streaming, unchanged-arc merges and resource caps.
"""
from array import array
from bisect import bisect_left
from collections import Counter
import coarse_osm_car_conditional_speed_v1 as new
import coarse_osm_car_policy_v2 as old


class FieldColumn:
    def __init__(self,rows,column):self.rows,self.column=rows,column
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):return self.rows[index][self.column]


def closed_relation_nodes(elements,check=lambda:None):
    result=set();count=0;previous=0
    for element in elements:
        check();count+=1;assert count<=100000 and previous<element['id'];previous=element['id']
        rule=old.restriction_policy(element);assert rule['status']=='closed-unsupported'
        if not rule['memberWays']:result.update(rule['memberNodes'])
        assert len(result)<=2000000
    return result,count


def prepare(ids,xy,anchors,flags,geometry,ways,arcs,records,relation_nodes,native_costs,check=lambda:None):
    assert 0<len(ids)<=50000000 and len(xy)==2*len(ids)
    assert 0<len(anchors)<=len(ids) and len(flags)==len(anchors) and len(ways)<=5000000 and len(geometry)<2**32
    assert len(arcs)<=16000000 and len(relation_nodes)<=2000000
    way_ids=FieldColumn(ways,0);arc_ways=FieldColumn(arcs,2)
    changed_ways={};changed_flags={};added=[];counts=Counter();previous=None
    def exact(values,value):
        at=bisect_left(values,value);return at if at<len(values) and values[at]==value else None
    for record in records:
        check();kind=record['type'];identity=record['id'];key=(0 if kind=='node' else 1,identity)
        assert kind in ('node','way') and (previous is None or key>previous);previous=key
        counts['records']+=1;assert counts['records']<=250000
        tags=record['tags']
        if kind=='node':
            a,b=old.node_policy(tags),new.node_policy(tags)
            assert a['blocked'] and not b['blocked'] and a['signal']==b['signal'] and a['tagged']==b['tagged']
            counts['changedSourceNodes']+=1;node=exact(ids,identity)
            if node is None:counts['changedNodesOutsideSelectedGraph']+=1;continue
            anchor=exact(anchors,node);assert anchor is not None,'Tagged selected node must be an original anchor'
            expected=1|4|(2 if a['signal'] else 0);assert flags[anchor]==expected
            if identity in relation_nodes:counts['changedNodesKeptClosedByRelation']+=1;continue
            changed_flags[anchor]=flags[anchor]&~1;counts['changedGraphNodeFlags']+=1;continue
        a,b=old.way_policy(tags),new.way_policy(tags)
        assert a.reason is not None and b.reason is None
        i=exact(way_ids,identity);assert i is not None and ways[i][1:3]==(0.,0.)
        pos=bisect_left(arc_ways,i);assert pos==len(arcs) or arc_ways[pos]!=i,'Old excluded way has no existing preclosure arc'
        row=ways[i];old_flag=row[3]
        assert old_flag>>8==5 and old_flag&15==0,'Only conditional closures can be restored'
        role=(old_flag>>4)&15
        assert old.POLICY['roles'][role]==tags['highway']
        directions=int(b.forward is not None)|(int(b.backward is not None)<<1)
        defaults=int(b.forward_default)|(int(b.backward_default)<<1)
        changed_ways[i]=(identity,b.forward or 0.,b.backward or 0.,directions|(defaults<<2)|(role<<4),row[4])
        start=0 if i==0 else ways[i-1][4];end=row[4];assert 2<=end-start<=2000000 and end<=len(geometry)
        chain=array('I',(geometry[p] for p in range(start,end)));cuts=[]
        for j,node in enumerate(chain):
            assert 0<=node<len(ids)
            anchor=exact(anchors,node)
            if anchor is not None:cuts.append((j,anchor))
        assert cuts[0][0]==0 and cuts[-1][0]==len(chain)-1
        coordinates=array('i');same=bytearray()
        for left,right in zip(chain,chain[1:]):
            coordinates.extend((xy[2*left],xy[2*left+1],xy[2*right],xy[2*right+1]));same.append(int(left==right))
        prices={direction:native_costs.costs(coordinates,array('d',[speed])*len(same),same) for direction,speed in ((1,b.forward),(-1,b.backward)) if speed is not None}
        for (first,tail),(last,head) in zip(cuts,cuts[1:]):
            if all(same[first:last]):continue
            for direction in (1,-1):
                if direction not in prices:continue
                ms,ticks=native_costs.sum(prices[direction][first:last]);assert ms>0 and ticks==(ms+124)//125
                added.append((tail if direction==1 else head,head if direction==1 else tail,i,first,last,direction,ms));assert len(added)<=1000000
        counts['changedGraphWays']+=1;counts['newPreClosureArcs']=len(added)
    assert len(changed_ways)==counts['changedGraphWays'] and len(changed_flags)==counts['changedGraphNodeFlags']
    return {'wayRows':changed_ways,'nodeFlags':changed_flags,'arcs':added,'counts':dict(counts)}
