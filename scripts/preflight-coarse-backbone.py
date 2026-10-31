"""One frozen offline national source-connectivity/storage preflight, not a router."""
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

from coarse_backbone import Components, VertexProbes, component_summary, quantized_deltas, sections
from coarse_census import ROOT, load_tool, part_key, road_parts
from coarse_path_features import distance_km

PLAN = ROOT / 'docs/evidence/coarse-backbone-preflight-2026-10-25/plan.json'
PLAN_SHA = '56f9d1ac9fb1d0ff782ccbd09479ae90b3076b9ddf59a559c2ced2f1f98bcf54'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1048576):
            h.update(block)
    return h.hexdigest()


def run(output):
    started = time.perf_counter()
    assert digest(PLAN) == PLAN_SHA
    plan = json.loads(PLAN.read_text())
    for name, expected in plan['inputs'].items():
        assert digest(ROOT / name) == expected, name
    output = output.resolve()
    assert output.is_relative_to(ROOT / 'data/coarse-quality')
    output.mkdir()  # Refuse all existing runs, including failures.
    (output/'plan.json').write_bytes(PLAN.read_bytes())
    assert shutil.disk_usage(output).free >= plan['resourceLimits']['minimumFreeDiskBytes']
    manifest = json.loads((ROOT/'data/coarse-sources/tiger-2026/national-v1/sources.json').read_text())
    sources = sorted(manifest['sources'], key=lambda source: source['sha256'])
    assert len(sources) == 49
    shapefile, _ = load_tool('docs/evidence/coarse-source-2026-10-22/tool.json')

    def guard():
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        assert rss <= plan['resourceLimits']['maximumProducerRssBytes'], 'Producer RSS guard'
        assert time.perf_counter()-started <= plan['resourceLimits']['maximumSeconds'], 'Producer time guard'
        return rss

    def parts(counts):
        seen = set()
        for i, source in enumerate(sources):
            for part in road_parts(source, shapefile):
                counts['parts'] += 1
                identity = part_key(part)
                if identity in seen:
                    counts['duplicates'] += 1
                    continue
                seen.add(identity)
                assert len(part['points']) >= 2
                counts['uniqueParts'] += 1
                yield part
            guard()
            print(f"Source pass {i+1}/49", file=sys.stderr, flush=True)

    # First pass holds only exact original endpoints, not all source vertices.
    endpoints = set()
    first_counts = Counter()
    for part in parts(first_counts):
        endpoints.add(tuple(part['points'][0]))
        endpoints.add(tuple(part['points'][-1]))
    assert first_counts['parts'] == plan['sourcePolicy']['partsBeforeExactDeduplication']
    assert first_counts['duplicates'] == plan['sourcePolicy']['exactDuplicateParts']
    ordered = sorted(endpoints)
    nodes = {point: i for i, point in enumerate(ordered)}
    del endpoints
    endpoint_uf, split_uf = Components(len(nodes)), Components(len(nodes))
    node_coordinates = array('d', (value for point in ordered for value in point))
    del ordered
    old_start, old_end, old_lengths = array('I'), array('I'), array('d')
    arrays = {'nodeCoordinates': node_coordinates, 'arcFrom': array('I'), 'arcTo': array('I'),
              'arcRoadKm': array('d'), 'arcDeciseconds': array('I'), 'arcSpeedKph': array('B'),
              'arcFirstPoint': array('I'), 'arcLastPoint': array('I'),
              'partPointOffsets': array('I', [0]), 'pointDeltas': array('i')}
    benchmark = json.loads((ROOT/'docs/evidence/coarse-path-features-2026-10-24/comparison.json').read_text())
    coordinates = sorted({(row[key]['lon'], row[key]['lat']) for row in benchmark['rows'] for key in ['origin','destination']})
    probe_index = {p:i for i,p in enumerate(coordinates)}
    probes = VertexProbes(coordinates, plan['diagnostics']['probeRadiusKm'], plan['diagnostics']['probeIndexDegrees'])
    source_km = 0.
    max_error = [0., 0.]
    second_counts = Counter()
    speeds = plan['sourcePolicy']['classes']
    for part in parts(second_counts):
        points = part['points']
        a, b = nodes[tuple(points[0])], nodes[tuple(points[-1])]
        endpoint_uf.join(a, b)
        distances = [0.]
        for left, right in zip(points, points[1:]):
            distances.append(distances[-1] + distance_km(left, right))
        length = distances[-1]
        old_start.append(a); old_end.append(b); old_lengths.append(length)
        source_km += length
        first_point = arrays['partPointOffsets'][-1]
        arrays['partPointOffsets'].append(first_point + len(points))
        for point, delta in zip(points, quantized_deltas(points)):
            arrays['pointDeltas'].extend(delta)
            for axis in [0, 1]:
                max_error[axis] = max(max_error[axis], abs(round(point[axis]*100000)/100000 - point[axis]))
            probes.consider(point, a)
        speed = speeds[part['class']]
        for start, end, x, y in sections(points, nodes):
            km = distances[end]-distances[start]
            if km == 0:
                second_counts['zeroLengthSections'] += 1
                continue
            split_uf.join(x, y)
            for name, value in [('arcFrom',x), ('arcTo',y), ('arcRoadKm',km),
                                ('arcDeciseconds',max(1,math.ceil(km/speed*36000))), ('arcSpeedKph',speed),
                                ('arcFirstPoint',first_point+start), ('arcLastPoint',first_point+end)]:
                arrays[name].append(value)
    assert first_counts['parts'] == second_counts['parts']
    assert first_counts['duplicates'] == second_counts['duplicates']
    assert first_counts['uniqueParts'] == second_counts['uniqueParts']
    assert abs(sum(arrays['arcRoadKm'])-source_km) <= 1e-7 * max(1,source_km)
    assert all(cost/36000*speed + 1e-8 >= km for cost,speed,km in zip(arrays['arcDeciseconds'],arrays['arcSpeedKph'],arrays['arcRoadKm']))
    initial = component_summary(endpoint_uf, old_start, old_end, old_lengths)
    split = component_summary(split_uf, arrays['arcFrom'], arrays['arcTo'], arrays['arcRoadKm'])
    assert split['components'] <= initial['components']
    assert split['largestRoadLengthFraction'] + 1e-8 >= initial['largestRoadLengthFraction']
    for best in probes.best:
        if best is not None:
            best['componentRoot'] = split_uf.find(best.pop('node'))
    ledger = []
    for row in benchmark['rows']:
        record = {'id':f"{row['set']}/{row['id']}"}
        for key in ['origin','destination']:
            point = (row[key]['lon'],row[key]['lat'])
            record[key] = {'query':row[key], 'nearestSourceVertexWithin5Km':probes.best[probe_index[point]]}
        ledger.append(record)
    assert len(ledger) == 83
    matched = sum(record[key]['nearestSourceVertexWithin5Km'] is not None for record in ledger for key in ['origin','destination'])
    # Actual gzip files, projected base64 JSON size; no runtime artifact is created.
    packed = {}
    for name, values in arrays.items():
        if sys.byteorder != 'little':
            values.byteswap()
        path = output/f'{name}.bin.gz'
        with path.open('wb') as stream:
            with gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0,compresslevel=6) as compressed:
                view = memoryview(values).cast('B')
                for start in range(0,len(view),1048576):
                    compressed.write(view[start:start+1048576])
        packed[name] = {'path':str(path.relative_to(ROOT)), 'sha256':digest(path), 'typecode':values.typecode,
                        'elements':len(values), 'rawBytes':len(values)*values.itemsize,
                        'gzipBytes':path.stat().st_size, 'base64Bytes':4*((path.stat().st_size+2)//3)}
        guard()
    data = json.loads((ROOT/'src/server/data/coarse-grid-v9.json').read_text())
    removed_bytes = sum(len(json.dumps(data.pop(name),separators=(',',':')).encode()) for name in ['roadLayer','supplementalRoadVisits'])
    # Include JSON property names, quotes, encoding prefixes, commas, and a full metadata reserve.
    kept_bytes = len(json.dumps(data,separators=(',',':')).encode())+1
    new_bytes = sum(len(name)+2+1+2+5+record['base64Bytes']+1 for name,record in packed.items())+1024
    projected = kept_bytes+new_bytes+plan['advanceGates']['functionOverheadBytes']+plan['advanceGates']['integrationReserveBytes']
    gates = {'sourceAndLengthConservation':True,
             'largestComponent':split['largestRoadLengthFraction'] >= plan['advanceGates']['largestSplitComponentMinimumRoadLengthFraction'],
             'endpointProximity':matched/166 >= plan['advanceGates']['endpointProximityMinimumFraction'],
             'projectedFunction':projected <= plan['advanceGates']['projectedFunctionMaximumBytes']}
    report = {'planSha256':PLAN_SHA, 'sources':49, 'counts':dict(second_counts), 'nodes':len(nodes),
              'arcs':len(arrays['arcFrom']), 'sourceRoadKm':source_km,
              'endpointOnly':initial, 'splitAtSourceEndpoints':split,
              'uniqueProbeCoordinates':len(coordinates), 'probeEndpoints':166, 'matchedProbeEndpoints':matched,
              'all83Ledger':ledger, 'geometryCoordinateErrorDegrees':{'lon':max_error[0],'lat':max_error[1]},
              'packedArrays':packed, 'retainedPrototypeArrayBytes':sum(v['rawBytes'] for v in packed.values()),
              'storageForecast':{'keptV9JsonBytes':kept_bytes,'removedComponentValueBytes':removed_bytes,
                                 'newPackedJsonBytesIncludingMetadata':new_bytes,
                                 'functionOverheadBytes':plan['advanceGates']['functionOverheadBytes'],
                                 'integrationReserveBytes':plan['advanceGates']['integrationReserveBytes'],
                                 'projectedFunctionBytes':projected},
              'gates':gates, 'advanceToRoutingPrototype':all(gates.values()),
              'wallSeconds':time.perf_counter()-started,'producerMaxRssBytes':guard(),
              'providerRequests':0,'sourceDownloads':0,'runtimeChanged':False,
              'scope':'National cached-source connectivity/storage preflight, not a routing graph accepted for app use, ETA result, road access verification or cloud runtime/memory/latency measurement. Endpoint/interior joins only; interior/interior-only junctions unresolved. All166 OD endpoints retained; source vertex proximity does not prove reachability.'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.output),indent=2))
