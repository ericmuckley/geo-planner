"""Concurrent host sampling; the worker separately guards every index write."""
from pathlib import Path
import stat

from coarse_timing_input import require


def owned_usage(root):
    root=Path(root);logical=allocated=entries=0
    for path in [root,*root.rglob('*')]:
        try:entry=path.lstat()
        except FileNotFoundError:
            # A checkpoint can be renamed, or a verified old shard removed,
            # after directory enumeration. Never retry the source operation.
            require(path!=root,'Full host owned root disappeared')
            continue
        require(stat.S_ISDIR(entry.st_mode) or stat.S_ISREG(entry.st_mode),'Full host special/symlink output')
        entries+=1;allocated+=entry.st_blocks*512
        if stat.S_ISREG(entry.st_mode):
            require(entry.st_nlink==1,'Full host hardlink output')
            logical+=entry.st_size
    return {'logicalBytes':logical,'allocatedBytes':allocated,'entries':entries,
            'conservativeAllocatedBytes':allocated+entries*8192+1048576}
