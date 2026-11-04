"""Compare cached provider endpoints with raw/simplified geography, without queries."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_coarse_grid as source

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def in_ring(point, ring):
    x, y = point
    inside = False
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y-a[1]) * (b[0]-a[0]) / (b[1]-a[1])
            if x < crossing:
                inside = not inside
    return inside


def in_polygon(point, polygon):
    return in_ring(point, polygon[0]) and not any(in_ring(point, r) for r in polygon[1:])


def meters(a, b):
    x, y = map(math.radians, a)
    u, v = map(math.radians, b)
    h = math.sin((v-y)/2)**2 + math.cos(y)*math.cos(v)*math.sin((u-x)/2)**2
    return 12742000 * math.asin(math.sqrt(min(1, h)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    recipe = REPO / args.plan
    assert sha(recipe) == args.pin
    plan = json.loads(recipe.read_bytes())
    for name, pin in plan['bindings'].items():
        assert sha(REPO / name) == pin, name
    countries = source.load('countries')
    country = next(f for f in countries if f['properties']['ADM0_A3'] == 'USA')
    boundary = [p for p in source.polygons(country['geometry']) if any(source.inside_bounds(x) for x in p[0])]
    lakes = [(f['properties'].get('name'), p) for f in source.load('lakes') for p in source.polygons(f['geometry']) if any(source.inside_bounds(x) for x in p[0])]
    simplified_country = [[source.simplify(r) for r in p] for p in boundary]
    simplified_lakes = [(name, [source.simplify(r) for r in p]) for name, p in lakes]

    def classify(point):
        return {'rawInCountry': any(in_polygon(point, p) for p in boundary),
                'simplifiedInCountry': any(in_polygon(point, p) for p in simplified_country),
                'rawLakes': [name for name, p in lakes if in_polygon(point, p)],
                'simplifiedLakes': [name for name, p in simplified_lakes if in_polygon(point, p)]}

    inputs = json.loads((REPO / plan['connections']).read_bytes())
    assert len(inputs) == 79
    input_rows = [{'coordinate': r['coordinate'], 'supported': r['connection'] is not None,
                   'geography': classify(r['coordinate'])} for r in inputs]
    reference_rows = []
    for bundle in plan['bundles']:
        root = REPO / bundle
        queries = json.loads((root / 'plan.json').read_bytes())['queries']
        for i, query in enumerate(queries):
            request = json.loads((root / f'{i:02d}-request.json').read_bytes())
            response = json.loads((root / f'{i:02d}-response.txt').read_bytes())
            feature = response['features'][0]
            assert feature['geometry']['type'] == 'LineString'
            line = feature['geometry']['coordinates']
            endpoints = [line[0][:2], line[-1][:2]]
            assert request['radiuses'] == [350, 350]
            reference_rows.append({'id': query['id'].split('/', 1)[-1],
                'requested': request['coordinates'], 'returned': endpoints,
                'snapMeters': [meters(a, b) for a, b in zip(request['coordinates'], endpoints)],
                'returnedGeography': [classify(p) for p in endpoints],
                'summary': feature['properties']['summary'],
                'requestPreference': request.get('preference'),
                'responsePreference': response['metadata']['query'].get('preference'),
                'systemMessage': response['metadata'].get('system_message'),
                'warnings': feature['properties'].get('warnings')})
    assert len(reference_rows) == len({r['id'] for r in reference_rows}) == 83
    report = {'status': 'saved_input_raw_geography_diagnostic_complete', 'recipeSha256': args.pin,
              'inputs': input_rows, 'references': reference_rows,
              'systemMessages': dict(Counter(r['systemMessage'] or 'missing' for r in reference_rows)),
              'providerRequests': 0, 'policyChanged': False,
              'scope': 'Raw cached Natural Earth source, its existing simplification and saved ORS endpoints only. Returned points are provider-network evidence, not independent real-world shoreline/legality proof. No source repair or new snap/access allowance.'}
    with (REPO / plan['output']).open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'inputs': len(input_rows), 'references': len(reference_rows), 'systemMessages': report['systemMessages']}))


if __name__ == '__main__':
    main()
