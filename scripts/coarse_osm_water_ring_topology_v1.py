"""Conservative native-ID chain prototype; not polygon/OSM-area validation."""
from collections import defaultdict

from coarse_timing_input import require


def join_degree_two(segments):
    """Return closed way chains only when endpoint topology has no branch.

    Segments are (way ID, first node ID, last node ID, reference count). Closed
    chains still need complete geometry, distinct vertices, intersections,
    orientation, containment and source-role audits before polygon use.
    """
    seen=set();closed=[];opened=[];adjacency=defaultdict(list);short=[]
    for way,first,last,count in segments:
        require(all(type(v) is int and v>0 for v in (way,first,last,count)) and count>=2,'Water ring native segment fields')
        require(way not in seen,'Water ring duplicate member way occurrence');seen.add(way)
        if first==last:
            if count<4:short.append(way)
            else:closed.append([[way,1]])
        else:
            index=len(opened);opened.append((way,first,last,count))
            adjacency[first].append(index);adjacency[last].append(index)
    degrees=sorted([identity,len(edges)] for identity,edges in adjacency.items() if len(edges)!=2)
    if degrees or short:
        return {'closedChains':closed,'allMembersJoined':False,'endpointDegreesNeedingGeometryOrMissingClosure':degrees,
                'shortClosedMemberWayIds':short,'unjoinedOpenWayIds':[row[0] for row in opened],
                'polygonValidityEstablished':False}
    visited=set()
    for seed,(_,first,_,_) in enumerate(opened):
        if seed in visited:continue
        chain=[];current=first;edge=seed
        while True:
            require(edge not in visited,'Water ring unexpected reused chain edge');visited.add(edge)
            way,head,tail,_=opened[edge]
            require(current in (head,tail),'Water ring chain native endpoint continuity')
            direction=1 if current==head else -1
            chain.append([way,direction]);current=tail if direction==1 else head
            if current==first:break
            remaining=[candidate for candidate in adjacency[current] if candidate not in visited]
            require(len(remaining)==1,'Water ring exact unambiguous next edge');edge=remaining[0]
        closed.append(chain)
    require(len(visited)==len(opened),'Water ring complete member-edge accounting')
    return {'closedChains':closed,'allMembersJoined':True,'endpointDegreesNeedingGeometryOrMissingClosure':[],
            'shortClosedMemberWayIds':[],'unjoinedOpenWayIds':[],'polygonValidityEstablished':False}
