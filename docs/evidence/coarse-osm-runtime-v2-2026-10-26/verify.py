"""Read-only runtime investigation proof; never fetch/install/import native tools."""
from email.parser import BytesParser
import hashlib
import json
import lzma
from pathlib import Path
import re
import struct
import sys


folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(mapping, root):
    for name, digest in mapping.items(): assert sha(root / name) == digest, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
files(manifest, folder)
checks = load(folder / 'checks.json'); files(checks['producerFiles'], repo); files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    prior = repo / 'docs/evidence' / name
    assert sha(prior / 'sha256.json') == record['manifestSha256']
    previous = load(prior / 'sha256.json'); assert len(previous) == record['files']; files(previous, prior)
source = load(folder / 'cache-inspection-v2.json'); closure = load(folder / 'library-closure-inspection.json')
assert source['package'] == 'libexpat1 2.6.1-2ubuntu0.6 arm64\n' and source['bytes'] == 198712
assert source['sha256'] == 'b4b445a092ad711e535cfa7241974f709b716194c58227abc75b05e3a3bec7f7' and source['elfMachine'] == 183
assert hashlib.sha256(source['license'].encode()).hexdigest() == source['licenseSha256']
assert closure['glibc'] == 'glibc 2.34' and closure['exitCode'] == 0 and not closure['readerImported']
assert 'GLIBC_2.36' in closure['stdout'] and 'GLIBC_2.38' in closure['stdout'] and 'not found' in closure['stdout']
assert (folder / 'cache-inspection.json').stat().st_size == 0 and 'readelf' in load(folder / 'cache-inspection-failure.json')['error']
for record in load(folder / 'remaining-glibc-cache-inspection.json'):
    assert record['exitCode'] == 0 and json.loads(record['stdout'])['libraries'][0]['sha256'] == source['sha256']
for record in load(folder / 'other-cached-runtime-inspection.json'):
    assert record['exitCode'] == 0 and json.loads(record['stdout'])['paths'] == []
plan = load(folder / 'metadata-inspection-plan.json')
assert sha(folder / 'metadata-inspection-plan.json') == 'b686bf9919a7aa980514a6bc42382c4f3fff83de29dd032cc877070d37d08a66'
assert sha(repo / 'scripts/inspect_osm_runtime_package.py') == plan['scriptSha256']
metadata = folder / 'package-metadata'; ledger = load(metadata / 'ledger.json')
assert len(ledger) == 2 and sum(e['deliveredBytes'] for e in ledger) == 3640481
for i, (event, spec) in enumerate(zip(ledger, plan['requests']), 1):
    body = metadata / f'{i:03d}.bin'
    assert event['httpStatus'] == 200 and event['status'] == 'complete' and event['method'] == 'GET' and event['path'] == spec['path']
    assert body.stat().st_size == event['deliveredBytes'] <= spec['maxBytes'] and sha(body) == event['sha256']
index = metadata / '002.bin'; release = (metadata / '001.bin').read_text()
section = release.split('SHA256:\n', 1)[1]
binding = [line.split() for line in section.splitlines() if line.strip().endswith(' main/binary-arm64/Packages.xz')]
assert len(binding) == 1 and binding[0][0] == sha(index) and int(binding[0][1]) == index.stat().st_size == 3512436
decoder = lzma.LZMADecompressor(memlimit=67108864); raw = decoder.decompress(index.read_bytes(), max_length=67108865)
assert decoder.eof and not decoder.unused_data and len(raw) == 20328441 < 67108864
stanzas = [s for s in raw.split(b'\n\n') if re.search(rb'^Package: libexpat1$', s, re.M)]
assert len(stanzas) == 1
parsed = BytesParser().parsebytes(stanzas[0]); candidate = load(metadata / 'package-candidate.json')
for key in ('Package', 'Version', 'Architecture', 'Depends', 'Filename', 'Size', 'SHA256', 'Installed-Size'):
    assert parsed[key] == candidate['package'][key], key
proposal = load(folder / 'next-package-plan.json'); pin = proposal['package']
assert pin['name'] == parsed['Package'] == 'libexpat1' and pin['version'] == parsed['Version'] == '2.4.7-1ubuntu0.9'
assert pin['architecture'] == parsed['Architecture'] == 'arm64' and pin['declaredDepends'] == parsed['Depends'] == 'libc6 (>= 2.25)'
assert pin['exactBytes'] == int(parsed['Size']) == 83528 and pin['sha256'] == parsed['SHA256'] == 'b61d2bdf82134f6db0ba5c73d9cfe88805a64cbadbd0d0dffff8410958aab005'
assert pin['url'] == 'https://ports.ubuntu.com/ubuntu-ports/' + parsed['Filename']
assert not candidate['packageBinaryFetched'] and not candidate['repositorySignatureVerified'] and candidate['indexBoundToRelease']
summary = load(folder / 'summary.json')
assert not summary['actualSelectedPackageAbiQualified'] and not summary['nativePbfProofExecuted'] and not summary['packageBinaryAcquired'] and summary['v9Unchanged']
assert proposal['caps']['runtimePackageGetAttempts'] == 1 and proposal['caps']['totalHttpBodyBytes'] == 1048576
assert all(proposal['caps'][n] == 0 for n in ('wheelGetAttempts', 'metadataGetAttempts', 'roadGetAttempts', 'providerQueries', 'retries', 'redirects', 'paidSpend'))
local = '--local-assets' in sys.argv
if local:
    files(checks['assetFiles'], repo); files(checks['toolFiles'], repo)
    for path, roster in checks['completedOutputs'].items(): assert set(roster) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    inputs = repo / 'data/coarse-quality/us-osm-runtime-v2-inputs'
    assert sha(inputs / 'libexpat.so.1') == source['sha256'] and sha(inputs / 'copyright') == source['licenseSha256']
    header = (inputs / 'libexpat.so.1').read_bytes(); assert header[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<HH', header, 16) == (3, 183)
    root = repo / 'data/coarse-quality/us-osm-runtime-v2-metadata/metadata'
    for p in metadata.iterdir(): assert sha(root / p.name) == sha(p)
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']), 'priorSealedRuns': len(checks['priorSealedEvidence']),
    'allBindingsValid': True, 'localAssetsChecked': local, 'assetFiles': len(checks['assetFiles']), 'tools': len(checks['toolFiles']), 'completedOutputs': len(checks['completedOutputs']),
    'cachedCandidateCompatible': False, 'loaderExitZeroMismatchPreserved': True, 'linuxMetadataGets': 2, 'linuxMetadataBodyBytes': 3640481,
    'proposedPackageBytes': 83528, 'actualPackageAbiQualified': False, 'packageBinaryAcquired': False, 'v9Unchanged': True}, indent=2))
