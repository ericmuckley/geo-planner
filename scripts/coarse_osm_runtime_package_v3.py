"""Version3: validate unselected in-package links without extracting any symlink."""
from email.parser import BytesParser
import hashlib
from pathlib import Path, PurePosixPath
import re

from coarse_osm_runtime_package import ar_members, decompress, tar_entries
from coarse_timing_input import digest, require


def extract_runtime(archive, pin, root):
    archive = Path(archive); require(archive.stat().st_size == pin['exactBytes'] and digest(archive) == pin['sha256'], 'Runtime archive identity')
    members = ar_members(archive.read_bytes()); expanded = 0; tables = []
    for name, compressed in members:
        decoded = decompress(name, compressed, 8388608 - expanded); expanded += len(decoded); tables.append(tar_entries(decoded))
    control, data = tables
    require(sum(map(len, tables)) <= 128 and all(e['kind'] in ('file', 'directory') for e in control.values()), 'Runtime control links/count')
    require('control' in control and control['control']['kind'] == 'file', 'Missing Debian control')
    metadata = BytesParser().parsebytes(control['control']['body']); require(len(metadata.keys()) == len(set(k.lower() for k in metadata.keys())), 'Duplicate Debian control field')
    expected = {'Package': pin['name'], 'Version': pin['version'], 'Architecture': pin['architecture'], 'Depends': pin['declaredDepends']}
    require(all(metadata[k] == v for k, v in expected.items()), 'Runtime package identity/dependency drift')
    links = [p for p in data if p in ('lib/aarch64-linux-gnu/libexpat.so.1', 'usr/lib/aarch64-linux-gnu/libexpat.so.1')]
    require(len(links) == 1, 'Unique runtime SONAME location')
    link = links[0]; license = 'usr/share/doc/libexpat1/copyright'
    require(link in data and data[link]['kind'] == 'symlink' and re.fullmatch(r'libexpat\.so\.1\.\d+\.\d+', data[link]['link']), 'Runtime SONAME link')
    # Validate every link without creating or following links on the filesystem.
    for path, entry in data.items():
        if entry['kind'] != 'symlink': continue
        relative = PurePosixPath(entry['link'])
        require(entry['link'] and len(entry['link'].encode()) <= 1024 and not relative.is_absolute()
            and not any(part in ('', '.', '..') for part in entry['link'].split('/'))
            and not any(c in entry['link'] for c in ('\\', ':', '\x00')), 'Runtime symlink target escape')
        resolved = str(PurePosixPath(path).parent / relative)
        require(resolved in data and data[resolved]['kind'] == 'file', 'Runtime symlink must resolve to in-package regular file')
    target = str(PurePosixPath(link).parent / data[link]['link'])
    require(target in data and data[target]['kind'] == 'file' and license in data and data[license]['kind'] == 'file', 'Runtime library/copyright closure')
    library, copyright = data[target]['body'], data[license]['body']
    require(64 <= len(library) <= 4194304 and 0 < len(copyright) <= 65536, 'Runtime library/copyright cap')
    root = Path(root); root.mkdir()
    for name, body in [('libexpat.so.1', library), ('copyright', copyright)]:
        with (root / name).open('xb') as stream: stream.write(body)
    inventory = {group: {name: {'kind': e['kind'], 'link': e['link'], 'bytes': len(e['body']) if e['body'] is not None else 0,
        'sha256': hashlib.sha256(e['body']).hexdigest() if e['body'] is not None else None} for name, e in entries.items()} for group, entries in zip(('control', 'data'), tables)}
    return {'status': 'runtime_bundle_extracted', 'archiveSha256': pin['sha256'], 'package': expected, 'expandedTarBytes': expanded,
        'library': {'source': target, 'bytes': len(library), 'sha256': hashlib.sha256(library).hexdigest()},
        'copyright': {'source': license, 'bytes': len(copyright), 'sha256': hashlib.sha256(copyright).hexdigest()}, 'members': inventory, 'packageScriptsExecuted': False}
