"""Native runtime preflight. A successful ldd exit alone does not establish closure."""
import hashlib
from pathlib import Path
import re
import struct
import subprocess

from coarse_timing_input import require


def check_loader_result(code, stdout, stderr):
    output = stdout + stderr
    require(len(output.encode()) <= 65536, 'Loader diagnostic byte cap')
    require(code == 0 and not re.search(r'not found|undefined symbol|not a dynamic executable|statically linked', output, re.I),
        'Runtime dependency/version closure failed: ' + output[:2000])
    require('libc.so.6' in output, 'Missing runtime dependency diagnostics')
    return {'runtimeClosurePassed': True, 'loaderExitCode': code, 'output': output}


def inspect_library(path, expected_sha, *, run=subprocess.run):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 64 <= path.stat().st_size <= 4194304, 'Runtime library file/size')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha, 'Runtime library SHA binding')
    require(raw[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<HH', raw, 16) == (3, 183), 'Runtime requires little-endian ELF64 aarch64 shared object')
    result = run(['ldd', '-v', str(path)], capture_output=True, text=True, timeout=5)
    return {'libraryBytes': len(raw), 'librarySha256': expected_sha, **check_loader_result(result.returncode, result.stdout, result.stderr)}
