"""Confirm all cached DBF header fields with the already-pinned pyshp reader."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
plan = load(folder / 'schema-check-plan.json')
for name, expected in plan['inputs'].items():
    assert digest(repo / name) == expected, name
tool = load(repo / 'docs/evidence/coarse-source-2026-10-22/tool.json')
wheel = repo / tool['path']
assert digest(wheel) == tool['sha256']
sys.path.insert(0, str(wheel))
import shapefile
assert shapefile.__version__ == '2.3.1'
assert Path(shapefile.__file__).as_posix().startswith(str(wheel) + '/')
inventory = load(folder / 'inventory.json')
for row in inventory['censusPartitions']:
    with zipfile.ZipFile(repo / row['path']) as archive:
        name, = [n for n in archive.namelist() if n.endswith('.dbf')]
        with archive.open(name) as stream, shapefile.Reader(dbf=stream) as reader:
            assert [f[0] for f in reader.fields[1:]] == row['fieldNames']
assert {tuple(r['fieldNames']) for r in inventory['censusPartitions']} == {('LINEARID', 'FULLNAME', 'RTTYP', 'MTFCC')}
result = {'all49HeadersIndependentlyConfirmed': True, 'reader': 'pyshp 2.3.1, existing pinned wheel',
          'inventorySha256': digest(folder / 'inventory.json'), 'sourceBuilds': 0, 'routingQueries': 0}
with (folder / 'schema-check.json').open('x') as stream:
    stream.write(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
