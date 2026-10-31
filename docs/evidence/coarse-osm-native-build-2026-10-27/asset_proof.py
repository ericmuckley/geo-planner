"""Portable read-only asset hash; excludes directory sizes and symlink permission bits."""
import hashlib
import json
import os
from pathlib import Path
import stat


def snapshot(root, metadata=False):
    root=Path(root);hashed=hashlib.sha256();files=entries=logical=0;rows={}
    def walk(path):
        nonlocal files,entries,logical
        for p in sorted(path.iterdir(),key=lambda p:p.name):
            s=p.lstat();name=str(p.relative_to(root));entries+=1
            row={'path':name,'mode':stat.S_IMODE(s.st_mode),'size':s.st_size}
            if p.is_symlink():row['kind']='link';row['target']=os.readlink(p)
            elif p.is_dir():row['kind']='directory'
            else:
                assert stat.S_ISREG(s.st_mode);row['kind']='file';files+=1;logical+=s.st_size
            if metadata:rows[name]=row.copy()
            if row['kind']=='directory':row.pop('size');walk(p)
            elif row['kind']=='link':row.pop('mode')
            else:
                with p.open('rb') as stream:row['sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
            hashed.update((json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode())
    walk(root)
    value={'files':files,'entries':entries,'logicalFileBytes':logical,'portableTreeSha256':hashed.hexdigest()}
    return (value,rows) if metadata else value
