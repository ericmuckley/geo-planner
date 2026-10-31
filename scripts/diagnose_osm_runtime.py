"""Read-only shared-library inspection; does not import/install the native reader."""
import json
from pathlib import Path
import platform
import subprocess
import sys


def diagnose(site):
    results = []
    for extension in sorted(Path(site).rglob('*.so')):
        result = subprocess.run(['ldd', str(extension)], capture_output=True, text=True, timeout=3)
        text = result.stdout + result.stderr
        if len(text.encode()) > 32768: raise ValueError('ldd output cap')
        results.append({'extension': str(extension.relative_to(site)), 'exitCode': result.returncode, 'output': text,
            'missing': sorted({line.split('=>')[0].strip() for line in text.splitlines() if '=> not found' in line})})
    return {'python': platform.python_version(), 'machine': platform.machine(), 'scope': 'Read-only ldd inspection; no native import, installation or network.',
        'extensions': results, 'missingLibraries': sorted({name for record in results for name in record['missing']})}


if __name__ == '__main__': print(json.dumps(diagnose(sys.argv[1]), indent=2))
