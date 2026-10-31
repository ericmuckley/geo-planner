"""Verify saved records, arithmetic and bindings without loading/searching a graph."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path: json.loads(path.read_text())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def verify_files(files, root):
    for name, expected in files.items():
        assert digest(root/name) == expected, name

manifest = load(folder/'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*')
                         if p.is_file() and p.name != 'sha256.json'}
verify_files(manifest, folder)
checks = load(folder/'checks.json')
verify_files(checks['producerFiles'], repo)
verify_files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    base = repo/'docs/evidence'/name
    assert digest(base/'sha256.json') == record['manifestSha256']
    old = load(base/'sha256.json')
    assert len(old) == record['files']
    verify_files(old, base)
for name in ['plan.json', 'base-plan.json', 'next-cost-design.json']:
    for path, expected in load(folder/name)['inputs'].items():
        if not path.startswith('data/'):
            assert digest(repo/path) == expected, path
report = load(folder/'report.json')
base = load(folder/'base-report.json')
findings = load(folder/'findings.json')
assert report['planSha256'] == digest(folder/'plan.json')
assert base['planSha256'] == digest(folder/'base-plan.json')
assert report['checks']['missingOrs'] == report['checks']['missingValhalla'] == []
assert len(report['rows']) == len(report['providerInventory']) == len(report['missingDataAndCoverageLedger']) == 83
older = [row for row in report['rows'] if 'valhallaMinutes' in row]
assert len(older) == 35 and all(row['orsMinusValhallaMinutes'] > 0 for row in older)
assert statistics.median(row['orsMinusValhallaMinutes'] for row in older) == findings['orsMinusValhallaMedianMinutes']
assert statistics.median(row['orsToValhallaDistanceRatio'] for row in older) == findings['orsToValhallaMedianDistanceRatio']
warnings = Counter(row['ors']['systemMessage'] for row in report['providerInventory'])
assert dict(warnings) == report['providers']['orsSystemMessages'] == {findings['warning']: 83}
source_edges = json.loads(gzip.decompress((folder/'edge-audit.json.gz').read_bytes()))
base_edges = json.loads(gzip.decompress((folder/'base-edge-audit.json.gz').read_bytes()))
assert len(source_edges) == len(base_edges) == 83
assert sum(len(row['edges']) for row in source_edges) == 22316
assert sum(len(row['edges']) for row in base_edges) == 6576
counts = Counter(edge['sourceKind'] for row in base_edges for edge in row['edges'])
assert dict(counts) == base['edgeCountsBySourceKind'] == {'natural-earth': 6575, 'census': 1}
source_by_id = {row['id']: row['edges'] for row in source_edges}
base_by_id = {row['id']: row['edges'] for row in base_edges}
for row in report['rows']:
    costs = row['costs']
    assert abs(math.fsum(edge['minutes'] for edge in source_by_id[row['id']])-costs['detailedCensusMinutes']) < 1e-8
    assert abs(math.fsum(edge['minutes'] for edge in base_by_id[row['id']])-costs['coarseBaseRoadMinutes']) < 1e-8
    parts = ['detailedCensusMinutes', 'coarseBaseRoadMinutes', 'localMinutes', 'transferMinutes',
             'unresolvedOriginMinutes', 'unresolvedDestinationMinutes', 'unresolvedDirectRoadMinutes']
    assert abs(math.fsum(costs[name] for name in parts)-row['candidateMinutes']) < 1e-8
assert not report['checks']['runtimeChanged'] and not base['runtimeChanged']
assert report['checks']['newRoutingQueries'] == base['newRoutingQueries'] == 0
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo/path)) for p in (repo/path).rglob('*') if p.is_file()}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'all83OrsAnd35ValhallaRetained': True,
                  'detailedSourceEdgesVerified': 22316, 'baseEdgesVerified': 6576,
                  'v9Unchanged': True, 'newRoutingQueries': 0, 'providerRequests': 0}, indent=2))
