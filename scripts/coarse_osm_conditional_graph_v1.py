"""Small captured-fact augmentation; no source reader, national data or tuning."""
from dataclasses import asdict
import math
from coarse_osm_car_conditional_speed_v1 import way_policy
from coarse_osm_car_policy_v2 import way_policy as old_way_policy
from import_roads import distance_m


def augment(ids,xy,anchors,geometry,ways,raw_arcs,records,check=lambda:None):
    assert 0<len(ids)<=200000 and len(xy)==2*len(ids) and len(ways)<=50000
    assert len(raw_arcs)<=200000 and len(records)<=10000 and len(geometry)<=500000
    positions={way[0]:i for i,way in enumerate(ways)};assert len(positions)==len(ways)
    vertices={node:i for i,node in enumerate(anchors)};assert len(vertices)==len(anchors)
    updated=list(ways);arcs=list(raw_arcs);existing={a[2] for a in raw_arcs};seen=set();changed=[]
    offsets=[0,*[w[4] for w in ways]][:-1]
    for record in records:
        check();assert record['kind']=='way';identity=record['id'];assert identity not in seen;seen.add(identity)
        tags=record['tags'];before=asdict(old_way_policy(tags));after=asdict(way_policy(tags))
        assert before==record['before'] and after==record['after']
        assert record['eligibilityGained']==(before['reason'] is not None and after['reason'] is None)
        if not record['eligibilityGained']:continue
        i=positions[identity];assert i not in existing and ways[i][1:3]==(0.0,0.0)
        row=ways[i];updated[i]=(identity,after['forward'] or 0.0,after['backward'] or 0.0,*row[3:])
        chain=geometry[offsets[i]:row[4]];assert len(chain)>=2
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
        changed.append({'way':identity,'newPreClosureArcs':additions,'forwardKph':after['forward'],'backwardKph':after['backward'],'conditionalSpeedStatus':record['conditionalSpeedStatus']})
    assert arcs[:len(raw_arcs)]==list(raw_arcs)
    return updated,arcs,changed
