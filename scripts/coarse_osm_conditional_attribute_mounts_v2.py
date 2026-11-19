"""Validate the flat fact directory consumed by the unchanged arc annotator."""
from pathlib import PurePosixPath
import re


def validate_fact_mounts(mounts):
    groups = {}
    for destination in mounts.values():
        path = PurePosixPath(destination)
        if not destination.startswith('/facts/'):
            continue
        match = re.fullmatch(r'(ways|arcs|closures)-([0-9]{4})\.bin', path.name)
        if path.parent != PurePosixPath('/facts') or match is None:
            raise ValueError('Source annotation requires flat /facts/<field>-NNNN.bin mounts')
        groups.setdefault(match[1], []).append(int(match[2]))
    if set(groups) != {'ways', 'arcs', 'closures'} or any(sorted(parts) != list(range(len(parts))) for parts in groups.values()):
        raise ValueError('Source annotation requires all contiguous ways/arcs/closures groups')
