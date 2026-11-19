"""Small captured lane overlay; exact source prices and normalized way flags."""
from dataclasses import asdict
import math

from coarse_osm_car_conditional_speed_v1 import way_policy as previous_policy
from coarse_osm_car_explicit_lanes_v1 import POLICY, classify_way
from import_roads import distance_m


def augment(ids,xy,anchors,geometry,ways,raw_arcs,records,check=lambda:None):
    assert 0<len(ids)<=200000 and len(xy)==2*len(ids) and len(ways)<=50000
    assert len(raw_arcs)<=200000 and len(records)<=10000 and len(geometry)<=500000
    positions={way[0]:i for i,way in enumerate(ways)};assert len(positions)==len(ways)
    vertices={node:i for i,node in enumerate(anchors)};assert len(vertices)==len(anchors)
    updated=list(ways);arcs=list(raw_arcs);existing={a[2] for a in raw_arcs};seen=set();changed=[]
    for record in records:
        check();assert record['kind']=='way';identity=record['id'];assert identity not in seen;seen.add(identity)
        tags=record['tags'];before=asdict(previous_policy(tags));explanation=classify_way(tags);after=asdict(explanation['policy'])
        assert before==record['before'] and after==record['after']
        gained=before!=after
        assert record['eligibilityGained']==gained
        assert tuple(record['explicitOrdinaryLaneIndices'])==explanation['explicitOrdinaryLaneIndices']
        assert tuple(record['acceptedLaneKeys'])==explanation['acceptedLaneKeys']
        if not gained:continue
        assert before['reason']=='lane-access' and after['reason'] is None
        i=positions[identity];row=ways[i];assert i not in existing and row[1:3]==(0.,0.)
        assert row[3]>>8==6 and row[3]&15==0,'Source lane-access reason/direction/default flags'
        role=(row[3]>>4)&15;assert POLICY['roles'][role]==tags['highway']
        direction_flags=int(after['forward'] is not None)|(int(after['backward'] is not None)<<1)
        default_flags=int(after['forward_default'])|(int(after['backward_default'])<<1)
        updated[i]=(identity,after['forward'] or 0.,after['backward'] or 0.,direction_flags|(default_flags<<2)|(role<<4),row[4])
        start=0 if i==0 else ways[i-1][4];chain=geometry[start:row[4]];assert len(chain)>=2
        cuts=[j for j,node in enumerate(chain) if node in vertices]
        assert cuts[0]==0 and cuts[-1]==len(chain)-1
        additions=0
        for first,last in zip(cuts,cuts[1:]):
            nodes=chain[first:last+1]
            if all(node==nodes[0] for node in nodes):continue
            a,b=vertices[nodes[0]],vertices[nodes[-1]]
            for direction,key in ((1,'forward'),(-1,'backward')):
                speed=after[key]
                if speed is None:continue
                assert 0<speed<=160
                ms=0
                for left,right in zip(nodes,nodes[1:]):
                    p=[xy[2*left]/1e7,xy[2*left+1]/1e7];q=[xy[2*right]/1e7,xy[2*right+1]/1e7]
                    ms+=0 if ids[left]==ids[right] else max(1,math.ceil(distance_m(p,q)*3600/speed))
                assert ms>0
                arcs.append((a if direction==1 else b,b if direction==1 else a,i,first,last,direction,ms));additions+=1
                assert len(arcs)<=200000
        changed.append({'way':identity,'newPreClosureArcs':additions,'policy':after,
                        'explicitOrdinaryLaneIndices':explanation['explicitOrdinaryLaneIndices'],
                        'normalizedWayFlags':updated[i][3]})
    assert arcs[:len(raw_arcs)]==list(raw_arcs)
    return updated,arcs,changed
