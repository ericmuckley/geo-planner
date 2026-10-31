"""Single frozen protected25m source-geometry/storage preflight, never app routing."""
import argparse
from array import array
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import shutil
import sys
import time

from coarse_backbone import Components, component_summary, sections
from coarse_backbone_geometry import GeometryGraph
from coarse_census import ROOT, load_tool, part_key, road_parts
from coarse_path_features import distance_km

PLAN = ROOT/'docs/evidence/coarse-backbone-geometry-2026-10-25/plan.json'
PLAN_SHA = 'fb1f8cad561e791c55db31751e5b0897e3ba7de1ceca4c11bcb978226f2d2420'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1048576): result.update(block)
    return result.hexdigest()


def read_array(binding):
    path = ROOT/binding['path']
    assert digest(path) == binding['sha256']
    result = array(binding['typecode'])
    with gzip.open(path,'rb') as stream: result.frombytes(stream.read())
    if sys.byteorder != 'little': result.byteswap()
    assert len(result) == binding['elements']
    return result


def pack_array(values, path):
    is_array = isinstance(values,array)
    if is_array and sys.byteorder != 'little':
        values = values[:]; values.byteswap()
    view = memoryview(values).cast('B')
    with path.open('wb') as stream:
        with gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0,compresslevel=6) as compressed:
            for start in range(0,len(view),1048576): compressed.write(view[start:start+1048576])
    return {'path':str(path.relative_to(ROOT)),'sha256':digest(path),
            'typecode':values.typecode if is_array else 'B','elements':len(values),
            'rawBytes':len(view),'rawSha256':hashlib.sha256(view).hexdigest(),
            'gzipBytes':path.stat().st_size,'base64Bytes':4*((path.stat().st_size+2)//3)}


def run(output):
    started = time.perf_counter()
    assert digest(PLAN) == PLAN_SHA
    plan = json.loads(PLAN.read_text())
    for name, expected in plan['inputs'].items(): assert digest(ROOT/name) == expected, name
    output = output.resolve()
    assert output.is_relative_to(ROOT/'data/coarse-quality')
    output.mkdir()
    (output/'plan.json').write_bytes(PLAN.read_bytes())
    assert shutil.disk_usage(output).free >= plan['resources']['minimumFreeDiskBytes']
    old = json.loads((ROOT/'docs/evidence/coarse-backbone-preflight-2026-10-25/report.json').read_text())
    references = {name:read_array(old['packedArrays'][name]) for name in
                  ['nodeCoordinates','arcFrom','arcTo','arcRoadKm','arcDeciseconds','arcSpeedKph','partPointOffsets']}
    coordinates = references['nodeCoordinates']
    nodes = {tuple(coordinates[i:i+2]):i//2 for i in range(0,len(coordinates),2)}
    assert len(nodes) == plan['sources']['originalNodes']
    graph = GeometryGraph(coordinates)
    manifest = json.loads((ROOT/'data/coarse-sources/tiger-2026/national-v1/sources.json').read_text())
    sources = sorted(manifest['sources'],key=lambda row:row['sha256'])
    assert len(sources) == 49
    shapefile, _ = load_tool('docs/evidence/coarse-source-2026-10-22/tool.json')
    seen, counts = set(), Counter()
    parent = 0
    before_cells, after_cells, source_ids = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()

    def guard():
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        assert rss <= plan['resources']['maximumProducerRssBytes'], 'Source RSS guard'
        assert time.perf_counter()-started <= plan['resources']['maximumSeconds'], 'Source time guard'
        return rss

    proof_path, parts_path = output/'parents.jsonl.gz', output/'parts.jsonl.gz'
    with gzip.open(proof_path,'wt',encoding='utf8') as proof_file, gzip.open(parts_path,'wt',encoding='utf8') as parts_file:
        for partition, source in enumerate(sources):
            for part in road_parts(source,shapefile):
                counts['parts'] += 1
                identity = part_key(part)
                if identity in seen:
                    counts['duplicates'] += 1
                    continue
                seen.add(identity)
                part_index = counts['uniqueParts']
                counts['uniqueParts'] += 1
                points = part['points']
                source_ids.update(identity)
                assert len(points) == references['partPointOffsets'][part_index+1]-references['partPointOffsets'][part_index]
                counts['originalSourceVertices'] += len(points)
                cumulative = [0.]
                for a,b in zip(points,points[1:]): cumulative.append(cumulative[-1]+distance_km(a,b))
                first_parent = parent
                for start,end,a,b in sections(points,nodes):
                    km = cumulative[end]-cumulative[start]
                    if not km:
                        counts['zeroLengthParents'] += 1
                        continue
                    speed = plan['sources']['speeds'][part['class']]
                    cost = max(1,math.ceil(km/speed*36000))
                    assert references['arcFrom'][parent] == a and references['arcTo'][parent] == b
                    assert references['arcRoadKm'][parent] == km
                    assert references['arcDeciseconds'][parent] == cost and references['arcSpeedKph'][parent] == speed
                    record = graph.add_parent(points[start:end+1],a,b,km,cost,speed)
                    record.update({'parent':parent,'part':part_index,'start':start,'end':end})
                    before_cells.update(json.dumps([parent,record['sourceCells']],separators=(',',':')).encode())
                    after_cells.update(json.dumps([parent,record['resultCells']],separators=(',',':')).encode())
                    proof_file.write(json.dumps(record,separators=(',',':'))+'\n')
                    parent += 1
                graph.end_part()
                parts_file.write(json.dumps({'part':part_index,'geometrySha256':identity.hex(),
                    'sourceSha256':source['sha256'],'id':part['id'],'multipartIndex':part['part'],
                    'class':part['class'],'vertices':len(points),'firstParent':first_parent,
                    'lastParent':parent},separators=(',',':'))+'\n')
            guard()
            print(f"Geometry source {partition+1}/49; parents={parent}; arcs={len(graph.arrays['arcFrom'])}",file=sys.stderr,flush=True)
    assert parent == plan['sources']['originalArcs']
    for key in ['parts','duplicates','uniqueParts']: assert counts[key] == plan['sources'][key]
    assert counts['originalSourceVertices'] == references['partPointOffsets'][-1]
    print('Building sparse junction/cell indexes',file=sys.stderr,flush=True)
    graph.finish_indexes()
    assert set(graph.arrays) == set(plan['storage']['runtimeArrays'])
    arrays = graph.arrays
    union = Components(len(arrays['nodeCoordinates'])//2)
    for a,b in zip(arrays['arcFrom'],arrays['arcTo']): union.join(a,b)
    components = component_summary(union,arrays['arcFrom'],arrays['arcTo'],arrays['arcRoadKm'])
    del union
    guard()
    packed = {}
    for name,values in arrays.items():
        packed[name] = pack_array(values,output/f'{name}.bin.gz')
        guard()
    forecast = old['storageForecast']
    new_json_bytes = sum(len(name)+2+1+2+5+record['base64Bytes']+1 for name,record in packed.items())+1024
    projected = forecast['keptV9JsonBytes']+new_json_bytes+forecast['functionOverheadBytes']+forecast['integrationReserveBytes']
    gates = {'allSourceParentsReproduced':parent == 501493,
             'allPartVertexDenominators':counts['originalSourceVertices'] == 24450400,
             'deviation':graph.max_deviation_meters <= 25,
             'cellRosters':graph.cell_mismatches == 0 and before_cells.digest() == after_cells.digest(),
             'parentLengths':graph.maximum_parent_length_error <= 1e-10*max(references['arcRoadKm']),
             'parentMinutes':graph.maximum_parent_minutes_error <= 1e-8,
             'positivePhysicalCosts':graph.max_chord_undercharge_meters <= .001,
             'components':components['components'] == 3100,
             'componentLengthShare':abs(components['largestRoadLengthFraction']-.9854365119558087) <= 1e-10,
             'all166EndpointDenominators':old['probeEndpoints'] == 166 and len(old['all83Ledger']) == 83,
             'projectedFunction':projected <= 70000000}
    report = {'planSha256':PLAN_SHA,'designSha256':plan['designSha256'],'counts':dict(counts),
              'originalNodes':graph.original_nodes,'nodes':len(arrays['nodeCoordinates'])//2,
              'arcs':len(arrays['arcFrom']),'sourceParents':parent,'components':components,
              'maximumDeviationMeters':graph.max_deviation_meters,
              'maximumChordUnderchargeMeters':graph.max_chord_undercharge_meters,
              'maximumParentLengthErrorKm':graph.maximum_parent_length_error,
              'maximumParentMinutesError':graph.maximum_parent_minutes_error,
              'sourceCellRosterSha256':before_cells.hexdigest(),'resultCellRosterSha256':after_cells.hexdigest(),
              'cellRosterMismatches':graph.cell_mismatches,
              'expandedSourceVerticesIncludingCrossings':graph.expanded_vertices,
              'retainedVerticesIncludingArcEndpoints':graph.retained_vertices,
              'interiorRetainedVertices':len(arrays['interiorSourceKm']),
              'activeIndexedCells':len(arrays['cellIds']),
              'packedArrays':packed,'proofs':{str(path.relative_to(ROOT)):digest(path) for path in [proof_path,parts_path]},
              'probeLedgerBinding':'docs/evidence/coarse-backbone-preflight-2026-10-25/report.json; all83/166 retained verbatim, no probe selection',
              'storageForecast':{'keptV9JsonBytes':forecast['keptV9JsonBytes'],
                  'newPackedJsonBytesIncludingMetadata':new_json_bytes,
                  'functionOverheadBytes':forecast['functionOverheadBytes'],
                  'integrationReserveBytes':forecast['integrationReserveBytes'],
                  'projectedFunctionBytes':projected},
              'gates':gates,'geometryAndSizePassed':all(gates.values()),
              'independentQualificationPending':True,'wallSeconds':time.perf_counter()-started,
              'producerMaxRssBytes':guard(),'providerRequests':0,'sourceDownloads':0,'runtimeChanged':False,
              'scope':'One protected25m full-source geometry/storage preflight. Parent costs preserved; new degree2 weights apportioned from originals. Actual indexes counted; function remains a forecast, not a handler/package, route/accuracy result or runtime/cloud memory/latency qualification.'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.output),indent=2))
