"""Read-only proposal/query/provenance proof; no HTTP or producer execution."""
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlencode, urlsplit

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_files(files, root):
    for name, sha in files.items():
        assert digest(root / name) == sha, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
verify_files(manifest, folder)
checks = load(folder / 'checks.json')
verify_files(checks['producerFiles'], repo)
verify_files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    base = repo / 'docs/evidence' / name
    assert digest(base / 'sha256.json') == record['manifestSha256']
    previous = load(base / 'sha256.json')
    assert len(previous) == record['files']
    verify_files(previous, base)
local = '--local-assets' in sys.argv
proposal, decision, queries, sources = (load(folder / name) for name in ['proposal.json', 'decision.json', 'queries.json', 'sources.json'])
for record in [proposal, decision]:
    for path, sha in record['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == sha, path
old = load(repo / queries['sourceProposal'])
assert digest(repo / queries['sourceProposal']) == queries['sourceProposalSha256']
assert proposal['approachesReviewed'] == ['Overture cloud GeoParquet bbox extraction', 'OSM snapshot extracts through Overpass']
assert decision['approachesReviewed'] == 2 and decision['selectedApproaches'] == 1
assert len(queries['queries']) == proposal['windows']['count'] == 21
assert proposal['source']['snapshotUtc'] == queries['snapshotUtc'] == '2026-10-21T00:00:00Z'
assert proposal['windows']['ids'] == [w['id'] for w in old['selection']['windows']]
for q, w in zip(queries['queries'], old['selection']['windows'], strict=True):
    assert q['id'] == w['id'] and q['bbox'] == w['bbox']
    west, south, east, north = w['bbox']
    assert west < east and south < north
    query = (repo / q['path']).read_text()
    assert digest(repo / q['path']) == q['querySha256']
    encoded = urlencode({'data': query}).encode()
    assert hashlib.sha256(encoded).hexdigest() == q['formBodySha256'] and len(encoded) == q['formBodyBytes']
    assert f'way["highway"]({south!r},{west!r},{north!r},{east!r})->.roads;' in query
    assert '[date:"2026-10-21T00:00:00Z"]' in query
    assert 'node(w.roads)->.road_nodes;' in query and '.payload out meta;\n.payload out count;\n' in query
    assert 'rel(bw.roads)["type"="restriction"]' in query and 'rel(bn.road_nodes)["type"="restriction"]' in query
    assert query.count('out ') == 2 and 'out geom' not in query and 'around' not in query
caps = proposal['hardCaps']
assert caps['httpAttempts'] == caps['statusGets'] + caps['interpreterPosts'] == 42
assert caps['statusGets'] == caps['interpreterPosts'] == 21
assert caps['totalHttpBodyBytes'] == 536870912 and caps['toolDownloadBytes'] == caps['retries'] == caps['paidSpend'] == caps['routingProviderRequests'] == caps['databaseReadsWrites'] == 0
assert caps['maximumBodyBytesFromRequestPlan'] == 21 * (65536 + 1) + 21 * (16777216 + 1) == 353697834 < caps['totalHttpBodyBytes']
assert caps['clientMemoryBytes'] == 1073741824 and caps['swapBytes'] == 0 and caps['wallSeconds'] == 3600
assert caps['normalizedExtractBytes'] == 134217728 and caps['workingBytes'] == 2147483648 and caps['uniqueSourceElementsAllTypes'] == 250000
assert proposal['feasibilityGates'] == old['goNoGo'] and proposal['originalIntegrationGates'] == old['integration']
assert all(decision[k] == 0 for k in ['newRoadStatusInterpreterRequests', 'newToolBinaryDownloads', 'newRoutingProviderRequests', 'newMatcherRuns', 'databaseReadsWrites'])
assert not decision['runtimeChanged'] and not decision['sourceAdapterImplemented'] and not decision['originalFeasibilityQualified']
allowed = {'docs.overturemaps.org', 'dev.overpass-api.de', 'wiki.openstreetmap.org', 'www.openstreetmap.org'}
assert len(sources['sources']) == 11 and all(urlsplit(s['url']).hostname in allowed for s in sources['sources'])
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'approachesReviewed': 2, 'selectedDesigns': 1, 'unchangedWindows': 21, 'frozenQueryFiles': 21,
    'plannedHttpAttempts': 42, 'newDataRequests': 0, 'newToolDownloads': 0,
    'sourceFeasibilityQualified': False, 'v9Unchanged': True}, indent=2))
