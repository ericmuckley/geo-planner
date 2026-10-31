"""Read-only cached capability probe: no source, index, compiler build or network."""
import hashlib
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import zlib

sys.path.insert(0, '/tools/site')
import osmium
import osmium.index
import osmium.filter
import osmium.io


def fingerprint(path):
    with path.open('rb') as stream:
        return {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}


commands = {}
for name in ('gcc', 'g++', 'cc', 'c++', 'clang', 'clang++', 'cmake', 'make', 'pkg-config', 'osmium', 'osmconvert', 'osmfilter', 'rustc', 'cargo'):
    path = shutil.which(name)
    row = {'path': path}
    if path is not None:
        try:
            result = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=2)
            row.update(exitCode=result.returncode, stdout=result.stdout[:4096], stderr=result.stderr[:4096])
        except Exception as error:
            row.update(error=str(error)[:512])
    commands[name] = row

headers = {}
for name in ('/usr/include/zlib.h', '/usr/include/bzlib.h', '/usr/include/expat.h', '/usr/include/osmium',
             '/usr/local/include/osmium', '/usr/include/protozero', '/usr/local/include/protozero',
             '/usr/include/pybind11', '/usr/local/include/pybind11',
             str(Path(sysconfig.get_path('include')) / 'Python.h')):
    path = Path(name)
    headers[name] = {'exists': path.exists(), 'directory': path.is_dir()}
    if path.is_file():
        headers[name].update(fingerprint(path))

api = {}
for name, value in [('NodeLocationsForWays', osmium.NodeLocationsForWays), ('BaseHandler', osmium.BaseHandler),
                    ('BaseFilter', osmium.BaseFilter), ('IdTracker', osmium.IdTracker),
                    ('Reader', osmium.io.Reader), ('LocationTable', osmium.index.LocationTable)]:
    api[name] = {'doc': (inspect.getdoc(value) or '')[:2048], 'publicMembers': [n for n in dir(value) if not n.startswith('_')][:100]}

site = Path('/tools/site')
assert sum(p.is_file() for p in site.rglob('*')) == 182
native_files = {str(p.relative_to(site)): fingerprint(p) for p in sorted(site.rglob('*')) if p.is_file() and p.suffix in ('.h', '.hpp', '.pyi', '.so')}
result = {'python': sys.version, 'platform': platform.platform(), 'machine': platform.machine(),
    'sysconfig': {k: sysconfig.get_config_var(k) for k in ('CC', 'CXX', 'SOABI', 'EXT_SUFFIX')},
    'zlibCompileVersion': zlib.ZLIB_VERSION, 'zlibRuntimeVersion': zlib.ZLIB_RUNTIME_VERSION,
    'commands': commands, 'headers': headers, 'nativeFiles': native_files, 'apis': api,
    'mapTypes': osmium.index.map_types(), 'filters': [n for n in dir(osmium.filter) if not n.startswith('_')],
    'optionalBuildModules': {name: importlib.util.find_spec(name) is not None for name in ('pybind11', 'setuptools', 'wheel', 'cffi')},
    'memory': {name: (Path('/sys/fs/cgroup') / name).read_text().strip() for name in ('memory.max', 'memory.swap.max', 'pids.max', 'cpu.max')},
    'sourceObjectsRead': 0, 'sampleFilesRead': 0, 'compilations': 0, 'networkRequests': 0,
    'scope': 'Named cached command/header paths and installed public APIs only; unavailable commands/headers are not a whole-filesystem absence proof.'}
raw = json.dumps(result, indent=2) + '\n'
assert len(raw.encode()) < 131072
print(raw, end='')
