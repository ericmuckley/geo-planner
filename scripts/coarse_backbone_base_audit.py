"""Attribute captured coarse-base road costs to immutable v9 source proofs."""
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys


def link_key(a, b, width, height):
    if not 0 <= a < width*height or not 0 <= b < width*height:
        raise ValueError('Captured base edge outside grid')
    ax, ay, bx, by = a % width, a // width, b % width, b // width
    if max(abs(ax-bx), abs(ay-by)) != 1:
        raise ValueError('Captured base edge is not neighboring cells')
    a, b = sorted([a, b])
    direction = {1: 0, width+1: 1, width: 2, width-1: 3}.get(b-a)
    if direction is None:
        raise ValueError('Unsupported base edge')
    return a*4+direction


def attribute(edge, proofs, width, height):
    key = link_key(edge['from'], edge['target'], width, height)
    proof = proofs[key]
    if edge['minutes'] != proof['deciseconds']/600:
        raise ValueError('Captured base time differs from qualified source proof')
    road = proof['roadKm']/proof['speedKph']*60
    connector = proof['localKm']/proof['connectorSpeedKph']*60
    rounding = edge['minutes']-road-connector
    if not -1e-8 <= rounding <= 1/600+1e-8:
        raise ValueError('Base road/connector pricing does not reconcile')
    return {'key': key, 'sourceKind': proof['kind'], 'minutes': edge['minutes'],
            'roadKm': proof['roadKm'], 'connectorKm': proof['localKm'],
            'sourceRoadMinutes': road, 'connectorMinutes': connector, 'roundingMinutes': rounding,
            'speedKph': proof['speedKph'], 'connectorSpeedKph': proof['connectorSpeedKph'],
            'sourcePointA': proof['pointA'], 'sourcePointB': proof['pointB']}


def run(output, expected_plan):
    root = Path('docs/evidence/coarse-backbone-path-audit-2026-10-25')
    digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    load = lambda path: json.loads(Path(path).read_text())
    assert digest(root/'base-plan.json') == expected_plan
    plan = load(root/'base-plan.json')
    for path, expected in plan['inputs'].items():
        assert digest(path) == expected, path
    output = Path(output)
    assert output.resolve() == Path(plan['output']).resolve()
    output.mkdir()
    (output/'plan.json').write_bytes((root/'base-plan.json').read_bytes())
    paths = json.loads(gzip.decompress(Path(plan['paths']).read_bytes()))
    original = {row['id']: row for row in load(plan['audit'])['rows']}
    proofs = {row['key']: row for row in json.loads(gzip.decompress(Path(plan['proofs']).read_bytes()))}
    rows, all_edges = [], []
    totals = defaultdict(float)
    counts = defaultdict(int)
    for path in paths:
        details = [attribute(edge, proofs, plan['width'], plan['height']) for edge in path['edges']
                   if edge['kind'] == 'road' and 'arc' not in edge]
        measured = original[path['id']]
        base_total = math.fsum(row['minutes'] for row in details)
        assert abs(base_total-measured['costs']['coarseBaseRoadMinutes']) < 1e-8
        groups = {}
        for kind in sorted({row['sourceKind'] for row in details}):
            selected = [row for row in details if row['sourceKind'] == kind]
            group = {key: math.fsum(row[key] for row in selected) for key in
                     ['minutes', 'sourceRoadMinutes', 'connectorMinutes', 'roundingMinutes', 'roadKm', 'connectorKm']}
            group['edges'] = len(selected)
            groups[kind] = group
            totals[kind] += group['minutes']
            counts[kind] += len(selected)
        row = {'id': path['id'], 'set': measured['set'], 'candidateMinutes': path['pointMinutes'],
               'coarseBaseRoadMinutes': base_total, 'groups': groups,
               'detailedCensusMinutes': measured['costs']['detailedCensusMinutes'],
               'coarseCensusTimeShare': groups.get('census', {}).get('minutes', 0)/path['pointMinutes']}
        rows.append(row)
        all_edges.append({'id': path['id'], 'edges': details})
    assert len(rows) == 83 and {row['id'] for row in rows} == set(original)
    total = math.fsum(row['candidateMinutes'] for row in rows)
    report = {'planSha256': expected_plan, 'cases': 83, 'capturedBaseEdgesChecked': sum(counts.values()),
              'allBaseRoadCostsMatchQualifiedV9Proofs': True,
              'minutesBySourceKind': dict(totals), 'edgeCountsBySourceKind': dict(counts),
              'wholeCandidateTimeShareByBaseKind': {kind: minutes/total for kind, minutes in totals.items()},
              'casesUsingCoarseCensus': sum('census' in row['groups'] for row in rows),
              'rows': rows, 'newRoutingQueries': 0, 'runtimeChanged': False,
              'scope': 'Captured paths only. Exact source/connector lengths, pricing and kind from qualified v9 base-link proof; full base-road polyline geometry remains unresolved. A retained coarse Census link can merge road visits by base cell, but this audit does not isolate its causal ETA effect. No new candidate, source producer, speed change, provider/key/env/DB input or activation.'}
    for name, value in [('report.json', report), ('edge-audit.json.gz', all_edges)]:
        raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
        if name.endswith('.gz'):
            raw = gzip.compress(raw, mtime=0)
        with (output/name).open('xb') as stream:
            stream.write(raw)
    print(json.dumps({key: value for key, value in report.items() if key != 'rows'}, indent=2))


if __name__ == '__main__':
    run(*sys.argv[1:])
