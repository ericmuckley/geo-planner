"""Version3: one metadata snapshot per output entry tolerates atomic checkpoints."""
from pathlib import Path
import stat

from coarse_osm_data import (  # Frozen data semantics/resources remain unchanged.
    download_source, extract_source, memory_guard, resource_arithmetic, verify_completed_data, verify_worker_inputs,
    validate_plan as validate_v2,
)
from coarse_timing_input import require


def tree_bytes(root):
    total = 0
    for path in Path(root).rglob('*'):
        try: entry = path.lstat()
        except FileNotFoundError: continue
        require(stat.S_ISDIR(entry.st_mode) or stat.S_ISREG(entry.st_mode), 'Special or symlink data output: ' + str(path))
        if stat.S_ISREG(entry.st_mode): total += entry.st_size
    return total


def validate_plan(plan, proposal):
    require(plan['phase'] == 'national_input_v3' and plan['output'] == 'data/coarse-quality/us-osm-input-v3', 'Version3 phase/output drift')
    validate_v2(dict(plan, phase='national_input_v2'), dict(proposal, futureOutput='data/coarse-quality/us-osm-input-v3'))
