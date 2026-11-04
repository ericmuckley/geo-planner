"""Bound excluded source geometry for evidence only, never fill or repair it."""
from bisect import bisect_left
from collections import Counter

from analyze_osm_water_endpoints_v1 import output_rows,relations
from assemble_osm_water_polygons_v1 import member_counts
from coarse_osm_water_point_scan_v1 import query
from coarse_osm_water_reference_store_v1 import Reader
from coarse_timing_input import require

PASSED='strict_cached_kernel_geometry_and_source_replay_passed'
DEPENDENCY='source_member_way_not_independent_water_polygon'


def dependencies(identity,records):
    pending=[identity];seen=set();ways=set();missing=set()
    while pending:
        current=pending.pop()
        if current in seen:continue
        seen.add(current);row=records.get(current)
        if row is None:missing.add(current);continue
        for member in row['members']:
            if member['type']=='way':ways.add(member['ref'])
            elif member['type']=='relation':pending.append(member['ref'])
    return sorted(ways),sorted(missing)


def analyze(catalog,selected_ids,selected_counts,member_ids,endpoint_root,endpoint_report,polygon_root,polygon_report,root_relations,descendant_relations,coordinates,check=lambda:None):
    rejected={1:{},2:{}};statuses={1:Counter(),2:Counter(),3:Counter()}
    with Reader(polygon_root,polygon_report['polygons']['diagnosticStore']) as reader:
        for row in output_rows(reader):
            check();kind=row['kind'];statuses[kind][row['status']]+=1
            if kind in (1,2) and row['status'] not in (PASSED,DEPENDENCY):rejected[kind][row['id']]=row['status']
        require(reader.finished and {str(k):dict(v) for k,v in statuses.items()}==polygon_report['polygons']['statusCounts'],'Water exclusion complete diagnostic population')
    records={row['id']:row for row in relations(descendant_relations)}
    for row in relations(root_relations):records[row['id']]=row
    require(all(identity in records for identity in rejected[2]),'Water exclusion every rejected source root retained')
    counts=member_counts(endpoint_root,endpoint_report['endpointStore'],member_ids)
    def way_count(identity):
        rank=bisect_left(member_ids,identity)
        if rank<len(member_ids) and member_ids[rank]==identity:return counts[rank]
        rank=bisect_left(selected_ids,identity)
        require(rank<len(selected_ids) and selected_ids[rank]==identity,'Water exclusion source way population')
        return selected_counts[rank]
    features=[];points=0
    for kind in (1,2):
        for identity,status in sorted(rejected[kind].items()):
            check();ways,missing_relations=([identity],[]) if kind==1 else dependencies(identity,records)
            bounds=None;missing_ways=[];found=references=0
            for way in ways:
                count=way_count(way)
                if count==0:missing_ways.append(way);continue
                geometry=catalog.gather([(way,1)],count);require(len(geometry)==count,'Water exclusion every source reference accounted')
                found+=1;references+=count;points+=count
                for _,x,y in geometry:
                    if bounds is None:bounds=[x,y,x,y]
                    else:bounds=[min(bounds[0],x),min(bounds[1],y),max(bounds[2],x),max(bounds[3],y)]
            features.append({'kind':kind,'id':identity,'status':status,'knownSourceBoundsE7':bounds,'sourceWayCount':len(ways),
                             'availableSourceWays':found,'availableReferenceOccurrences':references,
                             'missingSourceWayIds':missing_ways,'missingSourceRelationIds':missing_relations,
                             'allReferencedSourceGeometryBounded':not missing_ways and not missing_relations and bounds is not None,
                             'rawRelationType':records[identity]['tags'].get('type','') if kind==2 else None})
    outputs=[]
    for coordinate in coordinates:
        px,py,scale,_,_=query(coordinate);hits=[]
        for feature in features:
            bounds=feature['knownSourceBoundsE7']
            if bounds and bounds[0]*scale<=px<=bounds[2]*scale and bounds[1]*scale<=py<=bounds[3]*scale:
                hits.append({'kind':feature['kind'],'id':feature['id'],'allReferencedSourceGeometryBounded':feature['allReferencedSourceGeometryBounded']})
        outputs.append({'coordinate':coordinate,'overlappingKnownExcludedSourceBounds':hits})
    unbounded=[{'kind':f['kind'],'id':f['id'],'rawRelationType':f['rawRelationType'],'missingSourceWayIds':f['missingSourceWayIds'],'missingSourceRelationIds':f['missingSourceRelationIds']} for f in features if not f['allReferencedSourceGeometryBounded']]
    return {'excludedStandaloneWays':len(rejected[1]),'excludedRootRelations':len(rejected[2]),'excludedFeatures':features,
            'sourceReferenceOccurrencesUsedForBounds':points,'unboundedOrSourceIncompleteFeatures':unbounded,'queries':outputs,
            'scope':'Conservative bounds of all available source-way geometry for every excluded standalone way/root relation. Roles/topology remain unqualified; absent members cannot be spatially bounded. Bounding-box exclusion/hit is not polygon validity, land evidence, a coverage exemption, mask/routing/ETA/app admission.'}
