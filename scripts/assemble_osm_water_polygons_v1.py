"""Saved-data polygon feasibility; no geography replacement or routing policy."""
from bisect import bisect_left
from collections import Counter
import json
import struct
import time

from analyze_osm_water_endpoints_v1 import output_rows
from coarse_osm_water_endpoints_v1 import ROW
from coarse_osm_water_reference_store_v1 import Budget,Shards,Reader
from coarse_timing_input import require

FEATURE=struct.Struct('<BQI')
RING=struct.Struct('<BII')
POINT=struct.Struct('<Qii')


def member_counts(root,report,member_ids):
    result=[]
    with Reader(root,report) as reader:
        for identity in member_ids:
            raw=reader.read(ROW.size);require(len(raw)==ROW.size,'Water polygon complete endpoint row')
            found,first,last,count,present=ROW.unpack(raw)
            require(found==identity and present in (0,1) and (present==1 or first==last==count==0),'Water polygon complete member count identity/missing')
            result.append(count if present else 0)
        require(not reader.read(1) and reader.finished,'Water polygon endpoint row EOF')
    return result


def audit_source_geometry(source,output):
    """Independent Python replay of every emitted native edge/role/coordinate."""
    coordinates={identity:(x,y) for _,nodes in source for identity,x,y in nodes}
    expected=Counter((role,min(a[0],b[0]),max(a[0],b[0])) for role,nodes in source for a,b in zip(nodes,nodes[1:]))
    actual=Counter();points=0
    for rank,row in enumerate(output):
        role,parent,nodes=row['role'],row['parent'],row['nodes'];points+=len(nodes)
        require(role in (0,1) and len(nodes)>=4 and nodes[0]==nodes[-1],'Water polygon independent output role/native closure')
        require((role==0 and parent==rank) or (role==1 and 0<=parent<rank and output[parent]['role']==0),'Water polygon independent parent role/order')
        for identity,x,y in nodes:require(coordinates.get(identity)==(x,y),'Water polygon independent every source node coordinate exact')
        for a,b in zip(nodes,nodes[1:]):actual[(role,min(a[0],b[0]),max(a[0],b[0]))]+=1
    require(expected==actual and points==sum(len(n) for _,n in source),'Water polygon independent every source edge/role/reference exact')
    return points


def write_geometry(writer,kind,identity,rings):
    writer.write(FEATURE.pack(kind,identity,len(rings)))
    for row in rings:
        writer.write(RING.pack(row['role'],row['parent'],len(row['nodes'])));raw=bytearray()
        for node in row['nodes']:
            raw.extend(POINT.pack(*node))
            if len(raw)==1048576:writer.write(bytes(raw));raw.clear()
        if raw:writer.write(bytes(raw))


def audit_saved(root,report,expected_features,expected_rings,expected_points,check):
    features=rings=points=0;last_kind=last_identity=0
    with Reader(root,report) as reader:
        while raw:=reader.read(FEATURE.size):
            check();require(len(raw)==FEATURE.size,'Water polygon saved feature header')
            kind,identity,count=FEATURE.unpack(raw)
            require(kind in (1,2) and kind>=last_kind and identity>0 and 0<count<=100000,'Water polygon saved feature fields')
            if kind==last_kind:require(identity>last_identity,'Water polygon saved feature identity order')
            last_kind,last_identity=kind,identity;features+=1;roles=[];object_points=0
            for rank in range(count):
                raw=reader.read(RING.size);require(len(raw)==RING.size,'Water polygon saved ring header')
                role,parent,size=RING.unpack(raw);require(role in (0,1) and 4<=size<=2000000,'Water polygon saved ring fields')
                require((role==0 and parent==rank) or (role==1 and 0<=parent<rank and roles[parent]==0),'Water polygon saved parent/order')
                remaining=size;first=last=None;signed_area=0
                while remaining:
                    amount=min(remaining,65536);raw=reader.read(amount*16);require(len(raw)==amount*16,'Water polygon saved exact points')
                    for node in POINT.iter_unpack(raw):
                        identity,x,y=node;require(0<identity<2**63 and -1800000000<=x<=1800000000 and -900000000<=y<=900000000,'Water polygon saved native/E7 domain')
                        if first is None:first=node
                        if last is not None:signed_area+=last[1]*y-x*last[2]
                        last=node
                    remaining-=amount
                require(first==last and ((role==0 and signed_area>0) or (role==1 and signed_area<0)),'Water polygon saved exact closure/orientation/area')
                roles.append(role);rings+=1;points+=size;object_points+=size
            require(object_points<=2000000,'Water polygon saved object point cap')
        require(reader.finished and (features,rings,points)==(expected_features,expected_rings,expected_points),'Water polygon saved complete population/EOF')
    return {'allSavedFeaturesReopened':features,'allSavedRingsReopened':rings,'allSavedNativeCoordinatesReopened':points}


def assemble(root,catalog,selected_ids,selected_counts,member_ids,endpoint_root,endpoint_report,check=lambda:None):
    began=time.monotonic();counts=member_counts(endpoint_root,endpoint_report['endpointStore'],member_ids)
    member_set=set(member_ids);statuses={1:Counter(),2:Counter(),3:Counter()}
    geometry=Shards(root,'water-polygons.native',Budget(1792*1048576));diagnostics=Shards(root,'water-polygon-diagnostics',Budget(128*1048576))
    feature_count=ring_count=point_count=diagnostic_count=0
    def emit(kind,identity,source=None,reason=None):
        nonlocal feature_count,ring_count,point_count,diagnostic_count
        check()
        if reason is None:
            require(source and sum(len(n) for _,n in source)<=2000000,'Water polygon complete bounded input geometry')
            result=catalog.assemble(source)
            if result['accepted']:
                point_count+=audit_source_geometry(source,result['rings']);feature_count+=1;ring_count+=len(result['rings'])
                write_geometry(geometry,kind,identity,result['rings']);reason='strict_cached_kernel_geometry_and_source_replay_passed'
            else:reason=result['reason']
        statuses[kind][reason]+=1;diagnostic_count+=1
        diagnostics.write((json.dumps({'kind':kind,'id':identity,'status':reason},separators=(',',':'))+'\n').encode())
    try:
        for identity,count in zip(selected_ids,selected_counts):
            if identity in member_set:emit(1,identity,reason='source_member_way_not_independent_water_polygon')
            elif count<4:emit(1,identity,reason='source_way_has_too_few_references')
            else:emit(1,identity,[(0,catalog.gather([(identity,1)],count))])
        with Reader(endpoint_root,endpoint_report['chainStore']) as reader:
            for row in output_rows(reader):
                if not row['rootWaterRelation']:emit(3,row['relationId'],reason='untagged_descendant_not_independent_root_water_feature');continue
                if row['status']!='explicit_role_degree2_closed_chains':emit(2,row['relationId'],reason='source_chain_'+row['status']);continue
                specs=[];total=0
                for role,name in ((0,'outer'),(1,'inner')):
                    for chain in row[name]['closedChains']:
                        length=1
                        for identity,_ in chain:
                            rank=bisect_left(member_ids,identity)
                            require(rank<len(member_ids) and member_ids[rank]==identity and counts[rank]>=2,'Water polygon complete source member reference count')
                            length+=counts[rank]-1
                        total+=length;specs.append((role,chain,length))
                if total>2000000 or len(specs)>100000:emit(2,row['relationId'],reason='source_object_exceeds_qualified_geometry_capacity');continue
                emit(2,row['relationId'],[(role,catalog.gather(chain,length)) for role,chain,length in specs])
            require(reader.finished,'Water polygon complete source-chain diagnostics EOF')
        geometry_report=geometry.finish();diagnostic_report=diagnostics.finish()
    finally:geometry.close();diagnostics.close()
    measured_seconds=time.monotonic()-began;audit_began=time.monotonic()
    reopened=audit_saved(root,geometry_report,feature_count,ring_count,point_count,check)
    reopened_diagnostics=0;reopened_statuses={1:Counter(),2:Counter(),3:Counter()}
    with Reader(root,diagnostic_report) as reader:
        for row in output_rows(reader):
            reopened_statuses[row['kind']][row['status']]+=1;reopened_diagnostics+=1
        require(reader.finished and reopened_diagnostics==diagnostic_count and reopened_statuses==statuses,'Water polygon complete diagnostic reopen/status audit')
    return {'geometryStore':geometry_report,'diagnosticStore':diagnostic_report,'statusCounts':{str(k):dict(v) for k,v in statuses.items()},
            'acceptedFeatures':feature_count,'acceptedRings':ring_count,'sourcePointsIndependentlyReplayed':point_count,
            'diagnosticsReopened':reopened_diagnostics,**reopened,'geometryAssemblySourceReplayAndOutputSeconds':measured_seconds,
            'savedOutputReopenAndFieldAuditSeconds':time.monotonic()-audit_began,
            'scope':'Pinned cached kernel geometry and full source-edge/role/coordinate preservation for accepted objects. Every tagged water way/root/descendant has a diagnostic. Ambiguous/source-gap objects stay explicit; tagged member ways are not independent polygons, preserving relation holes. No geographic coverage, geodetic/shoreline accuracy, mask policy, routing correction or app admission.'}
