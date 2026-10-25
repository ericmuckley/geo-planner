"""Read saved paths/source proofs; diagnose rather than tune a rejected candidate."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
EVALUATION = ROOT / 'data/coarse-quality/class-timing-evaluation-v1'
source_paths = ['docs/evidence/coarse-finer-2026-10-23/paths.json',
                'docs/evidence/coarse-frontier-reference-2026-10-23/paths.json.gz']
regional_paths = json.loads((ROOT / source_paths[0]).read_text())
frontier_paths = json.loads(gzip.decompress((ROOT / source_paths[1]).read_bytes()))
frontier_diag = json.loads((ROOT / 'docs/evidence/coarse-frontier-reference-2026-10-23/diagnostic.json').read_text())
frontier_report = json.loads((ROOT / 'docs/evidence/coarse-frontier-reference-2026-10-23/comparison.json').read_text())
evaluation = json.loads((EVALUATION / 'comparison.json').read_text())
original_refs = json.loads((ROOT / 'docs/evidence/coarse-quality-2026-10-22/comparison.json').read_text())
regional_refs = json.loads((ROOT / 'docs/evidence/coarse-regional-2026-10-22/comparison.json').read_text())
artifact = json.loads((ROOT / 'src/server/data/coarse-grid-v8.json').read_text())
width, size = artifact['width'], artifact['width'] * artifact['height']
proofs = []
for layer, folder, frozen in [('base', 'resolution-0025-base-v1', 'base-build.json'),
                               ('layer', 'resolution-0025-road-v1', 'road-build.json')]:
    binding = json.loads((ROOT / 'docs/evidence/coarse-finer-2026-10-23' / frozen).read_text())
    raw = (ROOT / 'data/coarse-quality' / folder / 'links.json.gz').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == binding['linkProof']['sha256']
    proofs.append({r['key']: r for r in json.loads(gzip.decompress(raw))})

def edge_key(a, b):
    a, b = sorted([a, b])
    delta = b - a
    return a * 4 + {1: 0, width + 1: 1, width: 2, width - 1: 3}[delta]

rows = []
for sample in evaluation['rows']:
    group, id_ = sample['set'], sample['id']
    if group == 'frontier':
        saved = next(r for r in frontier_diag['samples'] if r['id'] == id_)
        edges = next(r['path'] for r in frontier_paths if r['id'] == id_)
        endpoint_km = saved['originAttachment']['distanceKm'] + saved['destinationAttachment']['distanceKm']
        reference_km = next(r['reference']['distanceKm'] for r in frontier_report['cases'] if r['id'] == id_)
    else:
        saved = next(r for r in regional_paths[group] if r['id'] == id_)
        assert abs(saved['pointMinutes'] - sample['baseline']['pointMinutes']) < 1e-8
        edges = saved['path']
        endpoint_km = sum(saved[k] for k in ['originAccessRoadKm', 'originAccessLocalKm', 'destinationAccessRoadKm', 'destinationAccessLocalKm'])
        references = original_refs['samples'] if group == 'original' else regional_refs['samples']
        reference_km = next(r['referenceKm'] for r in references if r.get('id', r.get('name')) == id_)
    road_km = connector_km = other_km = 0
    internal_connector_minutes = 0
    for edge in edges:
        a, b = (edge['from'], edge['to']) if group == 'frontier' else (edge['cell'], edge['target'])
        if edge['kind'] != 'road':
            # Local/transfer costs are paid at25; rounding affects only tiny transfers.
            other_km += edge['minutes'] / 60 * 25
            continue
        in_layer = a >= size
        assert in_layer == (b >= size)
        proof = proofs[int(in_layer)][edge_key(a - (size if in_layer else 0), b - (size if in_layer else 0))]
        assert abs(proof['deciseconds'] / 600 - edge['minutes']) < 1e-8
        road_km += proof['roadKm']
        connector_km += proof['localKm']
        internal_connector_minutes += proof['localKm'] / (25 if proof['kind'] == 'census' else proof['speedKph']) * 60
    model_km = road_km + connector_km + other_km + endpoint_km
    rows.append({'set': group, 'id': id_, 'referenceEngine': 'ORS9.10.0' if group == 'frontier' else 'Valhalla3.9.1',
                 'referenceKm': reference_km, 'modelSourceAndConnectorKm': model_km,
                 'distanceRatio': model_km / reference_km, 'roadSourceKm': road_km,
                 'internalConnectorKm': connector_km, 'internalConnectorMinutes': internal_connector_minutes,
                 'baselineErrorMinutes': sample['baselineErrorMinutes'], 'candidateErrorMinutes': sample['candidateErrorMinutes']})
summary = {}
for group in ['frontier', 'original', 'regional']:
    selected = [r for r in rows if r['set'] == group]
    summary[group] = {'cases': len(selected),
                      'meanDistanceRatio': sum(r['distanceRatio'] for r in selected) / len(selected),
                      'meanInternalConnectorMinutes': sum(r['internalConnectorMinutes'] for r in selected) / len(selected),
                      'meanReferenceKm': sum(r['referenceKm'] for r in selected) / len(selected),
                      'meanSourceAndConnectorKm': sum(r['modelSourceAndConnectorKm'] for r in selected) / len(selected)}

# Six deterministic distance quantiles, frozen before any matched ORS outcome.
ordered = sorted([r for r in rows if r['set'] != 'frontier'], key=lambda r: (r['referenceKm'], r['set'], r['id']))
ranks = [i * (len(ordered) - 1) // 5 for i in range(6)]
control = []
for rank in ranks:
    chosen = ordered[rank]
    query = next(r for r in evaluation['rows'] if r['set'] == chosen['set'] and r['id'] == chosen['id'])
    control.append({'id': f"{chosen['set']}/{chosen['id']}", 'rankZeroBased': rank,
                    'existingValhallaMinutes': query['referenceMinutes'], 'existingValhallaKm': chosen['referenceKm'],
                    'v8Minutes': query['baseline']['pointMinutes'],
                    'request': {'coordinates': [[query['origin']['lon'], query['origin']['lat']], [query['destination']['lon'], query['destination']['lat']]],
                                'instructions': False, 'preference': 'fastest', 'radiuses': [350, 350],
                                'options': {'avoid_borders': 'all', 'avoid_features': ['ferries']}}})
print(json.dumps({'summary': summary, 'rows': rows,
    'referenceConfound': 'The48 frontier references use ORS9.10, while both35-route regional sets use Valhalla3.9.1. Provider/profile and geography/duration differ together, so the current datasets cannot separate those causes. Route-distance/connector sums describe different selected routes, not a causal decomposition of timing error.',
    'proposedMatchedControl': {'status': 'prepared, no provider call authorized or made', 'maximumRequests': 6,
        'endpoint': 'https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson',
        'selection': 'Six evenly spaced ranks0,6,13,20,27,34 after sorting all35 regional routes by referenceKm, then set/id. Named places are validation only; no query replacement after results.',
        'minimumIntervalMs': 6500, 'timeoutMs': 45000, 'retries': 0, 'paidSpendCapEuro': 0,
        'stopOnStatus': [401,403,429], 'queries': control,
        'purpose': 'Compare two independent reference engines on identical public OD pairs before choosing another generic timing rule. No automatic model correction or new accuracy qualification. Requires a separate explicit request budget and bounded tested capture helper.'},
    'scope': 'Offline saved-path/source-proof diagnosis of all83 cases; no search, key/env/DB read, model change or provider request. Local/transfer distance inferred from paid25km/h cost includes sub-second rounding. NE/Census road/connector source lengths are not actual driven distance or proof of which model is correct.'}, indent=2))
