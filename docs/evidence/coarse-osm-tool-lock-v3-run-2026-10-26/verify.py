"""Read-only successful metadata lock proof; no Docker, network or producer replay."""
import hashlib
import json
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())
canonical = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


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
plan = load(folder / 'execution-plan.json')
assert digest(folder / 'execution-plan.json') == 'bd5bb8358cbbe41005f762578de83aae8ad34b8549008efd7b772da1a3b69044'
verify_files(plan['inputs'], repo)
ledger, state, lock, audit, summary = (load(folder / n) for n in ['http/http-ledger.json', 'setup-state.json', 'lock.json', 'lock-audit.json', 'run-summary.json'])
assert len(ledger['events']) == 4 and not ledger['stopped'] and [e['url'] for e in ledger['events']] == [s['url'] for s in plan['specs']]
metadata = {'osmium': load(repo / 'docs/evidence/coarse-osm-offline-plan-2026-10-26/linux-metadata/pyosmium-json.bin'),
    'requests': load(repo / 'docs/evidence/coarse-osm-tool-lock-run-2026-10-26/http/001.bin')}
for i, (event, spec, name) in enumerate(zip(ledger['events'], plan['specs'], ['charset-normalizer', 'idna', 'urllib3', 'certifi']), 1):
    body = folder / 'http' / event['bodyFile']
    assert event['number'] == i and event['status'] == 200 and event['outcome'] == 'complete' and event['kind'] == 'metadata' and event['method'] == 'GET'
    assert body.stat().st_size == event['bodyBytes'] == int(event['headers']['content-length']) <= spec['maxBytes']
    assert digest(body) == event['bodySha256'] and hashlib.md5(body.read_bytes()).hexdigest() == event['bodyMd5']
    assert 0 <= event['finishedElapsed'] - event['startedElapsed'] < event['absoluteSeconds'] == 20
    metadata[name] = load(body)
assert ledger['receivedBodyBytes'] == sum(e['bodyBytes'] for e in ledger['events']) == summary['v3DeliveredMetadataBodyBytes'] == 2734589
assert ledger['bodyBytesByKind'] == {'metadata': 2734589, 'wheel': 0, 'pbf': 0}
assert summary['combinedDeliveredBodyBytes'] == summary['v2DeliveredMetadataBodyBytes'] + ledger['receivedBodyBytes'] == 2927562
assert summary['combinedAttempts'] == 6 and summary['meterElapsedSeconds'] == ledger['elapsedSeconds']
assert state == {'status': 'metadata_lock_ready_tools_not_fetched', 'packageCount': 6, 'toolBinaryDownloads': 0, 'pbfRequests': 0, 'sourceFeasibilityQualified': False, 'actualDecoderQualified': False}
assert len(lock['packages']) == len({p['name'] for p in lock['packages']}) == 6
assert {p['name'] for p in lock['packages']} == set(metadata)
for package in lock['packages']:
    raw = metadata[package['name']]
    assert raw['info']['name'].replace('_', '-').lower() == package['name'] and raw['info']['version'] == package['version']
    assert hashlib.sha256(canonical(raw)).hexdigest() == package['metadataSha256']
    candidate = next(f for f in raw['urls'] if f['filename'] == package['filename'])
    assert candidate['size'] == package['size'] and candidate['url'] == package['url'] and candidate['digests']['sha256'] == package['sha256']
assert sum(p['size'] for p in lock['packages']) == lock['toolArchiveBytes'] == audit['toolArchiveBytes'] == 2387936
assert audit['savedLockReconstructsFromCapturedCatalogues'] and audit['network'] == 'none'
assert hashlib.sha256(canonical(audit['supportedTags'])).hexdigest() == lock['supportedTagsSha256']
guards, container, cleanup = (load(folder / n) for n in ['resource-guards.json', 'container-result.json', 'cleanup.json'])
assert guards['memory'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0} and guards['independentWatchdogSeconds'] == 300
assert container['Image'] == plan['imageId'] and container['Limits'] == {'NetworkMode': 'bridge', 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True}
assert container['State']['ExitCode'] == 0 and not container['State']['OOMKilled'] and cleanup['removed']
assert not (folder / 'worker.log').read_bytes()
names = checks['completedOutputs'][plan['output']]
assert len(names) == summary['outputFiles'] == 13 and sum((folder / n).stat().st_size for n in names) == summary['outputFileBytes'] == 2747308
next_plan = load(folder / 'next-tool-setup-plan.json'); verify_files(next_plan['inputs'], repo)
assert next_plan['proposedCaps']['exactWheelArchiveBytes'] == lock['toolArchiveBytes']
assignment = next_plan['storageAssignment']
assert sum(assignment[k] for k in ['wheelArchives', 'validationUnpack', 'installedTree', 'tmp', 'reportsState']) == assignment['assignedBytes'] == 354709472
assert assignment['assignedBytes'] + assignment['slackInside512MiB'] == next_plan['proposedCaps']['workingBytesIncludingTmp']
assert len(next_plan['wheelSpecs']) == 6 and sum(s['exactBytes'] for s in next_plan['wheelSpecs']) == 2387936
assert not summary['actualNativeDecoderQualified'] and not summary['largerDataCapsOrPublisherStateActivated'] and not summary['dependenciesInstalled']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, roster in checks['completedOutputs'].items():
        assert set(roster) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    for n in names: assert digest(repo / plan['output'] / n) == digest(folder / n)
    sys.path.insert(0, str(repo / 'scripts'))
    from coarse_osm_bulk_transport import validate_lock
    from pip._vendor.packaging.tags import Tag
    validate_lock(lock, metadata, load(repo / 'docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json')['tools'],
        tags=[Tag(*s.split('-')) for s in audit['supportedTags']], environment=lock['targetEnvironment'])
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'v3MetadataAttempts': 4, 'v3MetadataBodyBytes': 2734589, 'combinedMetadataAttempts': 6,
    'combinedMetadataBodyBytes': 2927562, 'lockedPackages': 6, 'plannedWheelArchiveBytes': 2387936,
    'binariesFetched': False, 'nativeDecoderQualified': False, 'v9Unchanged': True}, indent=2))
