"""Diagnose preserved paths against cached references; never run routing or fit costs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from coarse_backbone_paths import MultiCorridorIndex, overlap
from coarse_path_features import polyline_samples
from analyze_osm_access_paths_v1 import summarize

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()



from analyze_osm_water_paths_v1 import source_exposure

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    plan_path = REPO / args.plan
    assert sha(plan_path) == args.pin
    plan = json.loads(plan_path.read_bytes())
    for name, pin in plan['bindings'].items():
        assert sha(REPO / name) == pin, name
    provider = {}
    for bundle in plan['bundles']:
        root = REPO / bundle
        for i, q in enumerate(json.loads((root/'plan.json').read_bytes())['queries']):
            provider[q['id'].split('/', 1)[-1]] = root / f'{i:02d}-response.txt'
    assert len(provider) == 83
    witness = json.loads((REPO / plan['witnessReport']).read_bytes())
    roster = json.loads((REPO / plan['witnessClosed']).read_bytes())['roster']
    attribute_report=json.loads((REPO/plan['attributeReport']).read_bytes())
    artifact=attribute_report['artifact'];compressed=(REPO/plan['attributeRoot']/artifact['file']).read_bytes()
    assert len(compressed)==artifact['bytes'] and hashlib.sha256(compressed).hexdigest()==artifact['sha256']
    encoded=gzip.decompress(compressed);assert len(encoded)==artifact['rawBytes'] and hashlib.sha256(encoded).hexdigest()==artifact['rawSha256']
    attributes=json.loads(encoded)
    old_graph=json.loads((REPO/plan['attributeGraphPlan']).read_bytes());new_graph=json.loads((REPO/plan['candidatePlan']).read_bytes())
    for key in ['coreManifestSha256','geometryManifestSha256']:assert old_graph[key]==new_graph[key]
    rows, unavailable = [], []
    known_arcs,unknown_arcs=set(),set()
    for item in witness['rows']:
        assert time.monotonic()-began < 600
        if 'unavailable' in item:
            unavailable.append(item)
            continue
        name = item['asset']['filename']
        path = REPO / plan['witnessRoot'] / name
        assert path.stat().st_size == roster[name]['bytes'] and sha(path) == roster[name]['sha256']
        raw = gzip.decompress(path.read_bytes())
        assert len(raw) <= 33554432 and hashlib.sha256(raw).hexdigest() == item['asset']['rawSha256']
        record = json.loads(raw)
        sample = record['sample']
        assert sample['id'] == item['id']
        feature = json.loads(provider[sample['id']].read_bytes())['features'][0]
        assert feature['geometry']['type'] == 'LineString'
        reference = [p[:2] for p in feature['geometry']['coordinates']]
        summary = feature['properties']['summary']
        assert abs(summary['duration']/60-sample['referenceMinutes']) < 1e-8
        parts = []
        if record['initialConnection'] is not None:
            c = record['initialConnection']
            parts.append([c['origin'], c['snap']['coordinate']])
        if record['roadGeometry'] is not None:
            parts.append(record['roadGeometry']['coordinates'])
        terminal = record['terminalConnection']
        parts.append([terminal['snap']['coordinate'], terminal['origin']])
        candidate_samples = [s for p in parts for s in polyline_samples(p, 1)]
        reference_samples = list(polyline_samples(reference, 1))
        candidate_km = sum(w for _, w in candidate_samples)
        reference_km = sum(w for _, w in reference_samples)
        components = record['components']
        assert sum(components.values()) == record['sumTicks'] == record['primaryRoadTicks']
        road_minutes = components['roadTravelTicks']/480
        road_km = item['retainedRoadMeters']/1000
        exposure=source_exposure(record,attributes);known_arcs.update(exposure['knownArcs']);unknown_arcs.update(exposure['unknownArcs'])
        exposure['knownArcCount']=len(exposure.pop('knownArcs'))
        row = {'id': sample['id'], 'set': sample['set'], 'kind': 'primary-road',
               'budgetMinutes': sample['budgetMinutes'], 'referenceMinutes': sample['referenceMinutes'],
               'candidateMinutes': record['sumTicks']/480,
               'signedMinutes': record['sumTicks']/480-sample['referenceMinutes'],
               'components': components, 'sourceSpeedExposure':exposure, 'nonRoadMinutes': sum(v for k, v in components.items() if k not in ('roadTravelTicks', 'signalTicks', 'reversalTicks'))/480,
               'retainedRoadKm': road_km, 'retainedFullGeometryKm': candidate_km,
               'providerSummaryKm': summary['distance']/1000, 'providerGeometryKm': reference_km,
               'roadDistanceRatio': road_km/(summary['distance']/1000),
               'fullGeometryDistanceRatio': candidate_km/reference_km,
               'roadAverageKph': road_km/(road_minutes/60) if road_minutes else None,
               'providerSummaryAverageKph': (summary['distance']/1000)/(summary['duration']/3600),
               'candidateWithinReference': overlap(candidate_samples, MultiCorridorIndex([reference]), (1, 3)),
               'referenceWithinCandidate': overlap(reference_samples, MultiCorridorIndex(parts), (1, 3))}
        rows.append(row)
    assert len(rows) == plan["expectedFinite"] == 82 and len(unavailable) == plan["expectedUnavailable"] == 1
    assert len({row["id"] for row in rows}) == 82
    report = {'status': 'saved_primary_road_geometry_cost_diagnosis_complete', 'recipeSha256': args.pin,
              'rows': rows, 'unavailable': unavailable, 'overall': summarize(rows),
              'sets': {s: summarize([r for r in rows if r['set'] == s]) for s in ('original', 'regional', 'frontier')},
              'kinds': {s: summarize([r for r in rows if r['kind'] == s]) for s in sorted({row['kind'] for row in rows})},
              'largestAbsoluteErrors': [r['id'] for r in sorted(rows, key=lambda r: abs(r['signedMinutes']), reverse=True)[:12]],
              'sourceSpeedAttributeUniqueKnownArcs':len(known_arcs),
              'sourceSpeedAttributeUniqueUnknownArcs':len(unknown_arcs),
              'sourceSpeedAttributeUnknownArcIds':sorted(unknown_arcs,key=int),
              'sourceSpeedTickTotals':{key:sum(row['sourceSpeedExposure'][key] for row in rows) for key in ['explicitTicks','defaultTicks','unknownTicks']},
              'providerRequests': 0, 'modelQueries': 0, 'policyChanged': False,
              'hostSeconds': time.monotonic()-began,
              'scope': 'All83 development cases retained;82primary-road paths and1null,not point-proxy/local-grid winners or a full accuracy evaluation. Every missing source attribute stays explicitly unknown. Cached speed attributes are reused only on the identical frozen graph IDs; source speed is a legal/default input, not observed driving speed. No new source read. Observed development routes only. Corridor overlap uses sealed1km segment-midpoint quadrature and1/3km radii, not an exact topology/permission proof. Retained geometry length is not original unsimplified road length. Paid initial/terminal connectors are not proof of a drivable local road. Different source dates/provider preferences also remain; no national accuracy, policy fit or app admission.'}
    with (REPO / plan['output']).open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'overall': report['overall'], 'hostSeconds': report['hostSeconds']}))


if __name__ == '__main__':
    main()
