"""Read-only offline proposal proof; no acquisition, Docker or producer replay."""
import datetime
import hashlib
import json
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_files(files, root):
    for name, sha in files.items():
        assert digest(root / name) == sha, name


def segment_intersects(a, b, box):
    left, bottom, right, top = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    low, high = 0., 1.
    for p, q in [(-dx, a[0] - left), (dx, right - a[0]), (-dy, a[1] - bottom), (dy, top - a[1])]:
        if p == 0:
            if q < 0:
                return False
        elif p < 0:
            low = max(low, q / p)
        else:
            high = min(high, q / p)
    return low <= high


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
proposal, capacity = load(folder / 'proposal.json'), load(folder / 'capacity.json')
verify_files(proposal['inputs'], repo)
verify_files(load(folder / 'next-implementation-plan.json')['inputs'], repo)
caps, arithmetic, source = proposal['proposedCaps'], proposal['resourceArithmetic'], proposal['source']
GiB, MiB = 1024 ** 3, 1024 ** 2
assert caps['totalHttpBodyBytes'] == 12 * GiB and caps['workingBytesIncludingTmp'] == 64 * GiB
assert caps['clientMemoryBytes'] == 4 * GiB and caps['swapBytes'] == 0 and caps['wallSeconds'] == 14400
assert caps['tmpBytes'] == 256 * MiB and caps['cpus'] == 2
assert caps['httpAttempts'] == caps['pbfGets'] + caps['wheelGets'] + caps['metadataGets'] == 17
assert caps['pbfGets'] == 1 and caps['wheelGets'] == 6 and caps['metadataGets'] == 10
assert caps['selectedUniqueTypedElements'] == 250000 and caps['selectedWindowElementOccurrences'] == 500000
assert caps['normalizedExtractBytes'] == 128 * MiB
assert caps['sqliteIndexBytesEach'] == caps['sqliteMaxPagesEach'] * caps['sqlitePageBytes'] == 24 * GiB
assert arithmetic['maximumPlannedBodyBytes'] == sum(arithmetic['networkComponents'].values()) == 12382412112
assert arithmetic['networkCapSlackBytes'] == caps['totalHttpBodyBytes'] - arithmetic['maximumPlannedBodyBytes'] == 502489776
assert arithmetic['assignedWorkingBytes'] == sum(arithmetic['storageComponents'].values()) == 65270488400
assert arithmetic['workingCapSlackBytes'] == caps['workingBytesIncludingTmp'] - arithmetic['assignedWorkingBytes'] == 3448988336
assert capacity['host']['workspaceDisk']['freeBytes'] - caps['requiredInitialFreeBytes'] == arithmetic['hostObservedFreeMinusRequiredBytes'] > 0
assert caps['requiredInitialFreeBytes'] == caps['workingBytesIncludingTmp'] + caps['hostFreeHeadroomBytes'] == 80 * GiB
assert capacity['docker']['memoryBytes'] >= arithmetic['minimumDockerMemoryBytes'] >= caps['clientMemoryBytes']
assert capacity['host']['physicalMemoryBytes'] >= arithmetic['minimumHostMemoryBytes']
assert capacity['docker']['cpus'] >= caps['cpus'] and not capacity['docker']['pyosmiumInstalled']
assert caps['scanObjectVisitsTotal'] == caps['fullObjectDecodePasses'] * sum(caps[k] for k in ['scanNodesPerPass', 'scanWaysPerPass', 'scanRelationsPerPass']) == 4440000000
original = load(repo / 'docs/evidence/coarse-timing-design-2026-10-25/data-input-proposal.json')
assert proposal['windows'] == [{'id': w['id'], 'bbox': w['bbox']} for w in original['selection']['windows']]
assert len(proposal['windows']) == 21 and not proposal['oldWindowsOrGatesChanged']
assert source['url'] == 'https://download.geofabrik.de/north-america/us-261025.osm.pbf' and source['listedBodyBytes'] == 12229320016
assert (folder / 'linux-metadata/dated-md5.bin').read_text().split() == [source['publisherMd5'], 'us-261025.osm.pbf']
old = datetime.datetime.fromisoformat(source['oldExactTimeQueryUtc'].replace('Z', '+00:00'))
new = datetime.datetime.fromisoformat(source['proposedPublisherReplicationStateUtc'].replace('Z', '+00:00'))
assert (new - old).total_seconds() == source['differenceSeconds'] == 422481
package = load(folder / 'linux-metadata/pyosmium-json.bin')
wheel = next(w for w in package['urls'] if w['filename'] == proposal['tools']['wheel']['filename'])
assert all(wheel[k] == v for k, v in proposal['tools']['wheel'].items())
assert wheel['size'] == 1729855 and wheel['digests']['sha256'] == proposal['tools']['wheelSha256']
assert package['info']['version'] == '4.3.2' and 'requests' in package['info']['requires_dist']
host_events = load(folder / 'metadata-ledger.json')['events']
linux_events = load(folder / 'linux-metadata-ledger.json')['events']
assert len(host_events) == 3 and len(linux_events) == 2
assert all(e['outcome'] == 'failed' and e['errorType'] == 'SSLCertVerificationError' and e['receivedBodyBytes'] == 0 for e in host_events)
assert all(e['outcome'] == 'complete' and e['status'] == 200 for e in linux_events)
for e in host_events + linux_events:
    body = folder / e['bodyFile']
    assert body.stat().st_size == e['receivedBodyBytes'] <= e['bodyLimitBytes']
    assert digest(body) == e['bodySha256'] and e['redirectsFollowed'] == 0
assert sum(e['receivedBodyBytes'] for e in host_events + linux_events) == 51238
sources = load(folder / 'sources.json')
assert sources['directMetadataRequests'] == 5 and sources['directMetadataManuallyRepeatedRequests'] == 2
assert sources['directMetadataFailedTlsRequests'] == 3 and sources['directMetadataDeliveredBodyBytes'] == 51238
assert sources['roadPbfRequests'] == sources['toolBinaryDownloads'] == sources['directMetadataAutomaticRetries'] == 0
fixtures = load(folder / 'synthetic-cases.json')
assert len(fixtures['geometryCases']) == 7
for case in fixtures['geometryCases']:
    pts = case['points']
    assert any(segment_intersects(a, b, fixtures['bbox']) for a, b in zip(pts, pts[1:])) == case['selected'], case['name']
assert all(not proposal[k] for k in ['executionReady', 'largerLimitsActivated', 'sourceSnapshotActivated', 'toolsFetchedOrInstalled', 'roadDataFetched'])
assert not proposal['tools']['lockComplete']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'proposalArithmeticCapacityMetadataAndSevenGeometryCasesValid': True, 'unchangedWindows': 21,
    'directMetadataAttempts': 5, 'directMetadataBodyBytes': 51238, 'roadOrToolPayloads': 0,
    'largerLimitsOrSnapshotActivated': False, 'executionReady': False,
    'plannedOutputCurrentlyExists': (repo / proposal['futureOutput']).exists(), 'v9Unchanged': True}, indent=2))
