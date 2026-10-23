"""Offline analysis of sealed reference responses and reconstructed v8 paths."""
import base64
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
EVIDENCE = Path(__file__).resolve().parent
RUN = EVIDENCE / 'reference'
DIAG = EVIDENCE
REPORT = EVIDENCE / 'comparison.json'
artifact = ROOT / 'src/server/data/coarse-grid-v8.json'
raw = artifact.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910'
data = json.loads(raw)
encoded = data['links']
links = gzip.decompress(base64.b64decode(encoded[5:])) if encoded.startswith('gzip:') else base64.b64decode(encoded)
width, size = data['width'], data['width'] * data['height']
diagnostic = json.loads((DIAG / 'diagnostic.json').read_text())
path_bytes = (DIAG / 'paths.json.gz').read_bytes()
assert hashlib.sha256(path_bytes).hexdigest() == diagnostic['pathSha256']
assert hashlib.sha256(REPORT.read_bytes()).hexdigest() == diagnostic['reportSha256']
paths = {r['id']: r['path'] for r in json.loads(gzip.decompress(path_bytes))}
report = json.loads(REPORT.read_text())
assert len(report['cases']) == len(diagnostic['samples']) == len(paths) == 48
samples = []
for row in diagnostic['samples']:
    tags = Counter()
    for edge in paths[row['id']]:
        if edge['kind'] != 'road':
            continue
        a, b = sorted([edge['from'], edge['to']])
        if a >= size:
            tag = 'Census-layer'
        else:
            assert b < size
            delta = b - a
            direction = {1: 0, width + 1: 1, width: 2, width - 1: 3}[delta]
            speed = links[a * 4 + direction]
            assert speed > 0
            tag = f'base-{speed}'
        tags[tag] += edge['minutes']
    assert abs(sum(tags.values()) - row['components']['roadMinutes']) < 1e-8
    samples.append({
        'id': row['id'],
        'differenceMinutes': row['differenceMinutes'],
        'componentsMinutes': row['components'],
        'roadMinutesByStoredSpeedTag': dict(sorted(tags.items())),
        'chordToReferenceDistanceRatio': (row['roadChordKm'] + row['localChordKm'] + row['transferChordKm']) / row['reference']['distanceKm'],
    })

records = [json.loads(p.read_text()) for p in sorted(RUN.glob('*-result.json'))]
starts = [datetime.fromisoformat(r['startedAt'].replace('Z', '+00:00')) for r in records]
components = {k: sum(r['components'][k] for r in diagnostic['samples']) / 48 for k in diagnostic['samples'][0]['components']}
groups = {}
for name, subset in [('all', samples), ('modelFaster', [r for r in samples if r['differenceMinutes'] < 0]), ('modelSlower', [r for r in samples if r['differenceMinutes'] > 0])]:
    tags = Counter()
    for r in subset:
        tags.update(r['roadMinutesByStoredSpeedTag'])
    total = sum(tags.values())
    groups[name] = {'count': len(subset), 'roadTimeShareByStoredSpeedTag': {k: v / total for k, v in sorted(tags.items())}}

print(json.dumps({
    'requestCount': len(records),
    'statuses': dict(Counter(str(r['status']) for r in records)),
    'minimumStartIntervalMs': min((b - a).total_seconds() * 1000 for a, b in zip(starts, starts[1:])),
    'firstStart': records[0]['startedAt'],
    'lastFinish': records[-1]['finishedAt'],
    'firstReturnedQuotaRemaining': records[0]['headers'].get('x-ratelimit-remaining'),
    'lastReturnedQuotaRemaining': records[-1]['headers'].get('x-ratelimit-remaining'),
    'responseBytes': sum(r['bodyBytes'] for r in records),
    'maximumResponseBytes': max(r['bodyBytes'] for r in records),
    'bodyRedactions': sum(r['bodyRedacted'] for r in records),
    'maxSnapMeters': max(v for r in report['cases'] for v in r['reference']['snapMeters']),
    'averageComponentsMinutes': components,
    'roadTimeShareOfModel': sum(r['components']['roadMinutes'] for r in diagnostic['samples']) / sum(r['modelMinutes'] for r in diagnostic['samples']),
    'speedTagGroups': groups,
    'largestFastError': min(samples, key=lambda r: r['differenceMinutes']),
    'largestSlowError': max(samples, key=lambda r: r['differenceMinutes']),
    'samples': samples,
    'scope': 'Offline descriptive diagnostic only. Base link tags record the selected-cost speed bucket, not a current speed limit or proof of a particular source/class causally explaining error. Costs include source-arc/connector geometry; Census-layer links have no retained per-link speed tag. Chords are not road-polyline distance. Groups are conditioned on observed error, not independent prediction evidence. All 48 samples retained; no model or query correction fitted, no provider calls.',
}, indent=2))
