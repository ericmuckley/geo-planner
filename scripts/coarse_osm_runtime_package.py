"""Exact runtime-package transfer and bounded ar/tar inspection; no package scripts."""
import bz2
import ctypes
from email.parser import BytesParser
import hashlib
import http.client
import io
import lzma
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
import zlib

from coarse_osm_bulk_transport import Meter
from coarse_osm_input import NativeResponse, absolute_timeout
from coarse_timing_input import digest, require


URL = 'https://ports.ubuntu.com/ubuntu-ports/pool/main/e/expat/libexpat1_2.4.7-1ubuntu0.9_arm64.deb'
ZSTD_PATH = '/usr/lib64/libzstd.so.1.5.5'
ZSTD_SHA = '512958c830b5d563df9e9f245133f1bae1a614fc988c2cbd5bf80db5e0f2cfce'


class RuntimeHttps:
    def open(self, url, seconds, idle):
        require(url == URL, 'Only exact runtime package endpoint allowed')
        connection = http.client.HTTPSConnection('ports.ubuntu.com', 443, timeout=min(seconds, idle))
        try:
            connection.request('GET', url.removeprefix('https://ports.ubuntu.com'), headers={'Accept-Encoding': 'identity', 'Connection': 'close', 'User-Agent': 'geo-planner-runtime/2'})
            return NativeResponse(connection, connection.getresponse())
        except BaseException: connection.close(); raise


class RuntimeMeter(Meter):
    """Admit one new exact endpoint/kind; reuse sealed transfer/framing/error controls."""
    def __init__(self, root, pin, *, transport=None, clock=time.monotonic, alarm=absolute_timeout):
        require(pin['url'] == URL and pin['exactBytes'] == 83528 and pin['sha256'] == 'b61d2bdf82134f6db0ba5c73d9cfe88805a64cbadbd0d0dffff8410958aab005', 'Runtime pin drift')
        self.root = Path(root).resolve(); require(self.root.is_dir() and not any(self.root.iterdir()), 'Meter needs new empty output')
        self.specs = [{'url': URL, 'kind': 'runtime', 'maxBytes': 83528, 'exactBytes': 83528, 'sha256': pin['sha256'], 'seconds': 60}]
        self.caps = {'attempts': 1, 'totalBytes': 1048576, 'kindBytes': {'runtime': 1048576, 'metadata': 0, 'wheel': 0, 'pbf': 0},
            'wallSeconds': 600, 'idleSeconds': 20, 'workingBytes': 469762048, 'errorBytes': 65536}
        self.transport, self.clock, self.alarm = transport or RuntimeHttps(), clock, alarm
        self.started = clock(); self.events = []; self.body_bytes = 0
        self.by_kind = {'runtime': 0, 'metadata': 0, 'wheel': 0, 'pbf': 0}; self.failed = False; self.checkpoint()


def zstd_api():
    require(digest(ZSTD_PATH) == ZSTD_SHA, 'Cached Zstandard binding')
    api = ctypes.CDLL(ZSTD_PATH)
    for name, args, result in [
        ('ZSTD_versionNumber', [], ctypes.c_uint), ('ZSTD_isError', [ctypes.c_size_t], ctypes.c_uint),
        ('ZSTD_findFrameCompressedSize', [ctypes.c_void_p, ctypes.c_size_t], ctypes.c_size_t),
        ('ZSTD_getFrameContentSize', [ctypes.c_void_p, ctypes.c_size_t], ctypes.c_ulonglong),
        ('ZSTD_decompress', [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t], ctypes.c_size_t)]:
        function = getattr(api, name); function.argtypes = args; function.restype = result
    require(api.ZSTD_versionNumber() == 10505, 'Cached Zstandard version drift'); return api


def decompress(name, raw, limit):
    require(0 < limit <= 8388608, 'Archive expansion allowance')
    if name.endswith('.zst'):
        api = zstd_api(); length = api.ZSTD_findFrameCompressedSize(raw, len(raw))
        require(not api.ZSTD_isError(length) and length == len(raw), 'Zstandard frame/trailing data')
        size = api.ZSTD_getFrameContentSize(raw, len(raw))
        require(size != 2**64 - 2 and (size == 2**64 - 1 or size <= limit), 'Zstandard declared expansion cap')
        output = ctypes.create_string_buffer(limit)
        actual = api.ZSTD_decompress(output, limit, raw, len(raw))
        require(not api.ZSTD_isError(actual) and actual <= limit, 'Zstandard expansion/error')
        return output.raw[:actual]
    if name.endswith('.xz'): decoder = lzma.LZMADecompressor(memlimit=67108864)
    elif name.endswith('.gz'): decoder = zlib.decompressobj(31)
    elif name.endswith('.bz2'): decoder = bz2.BZ2Decompressor()
    else: raise ValueError('Unsupported runtime compression')
    value = decoder.decompress(raw, limit + 1)
    require(len(value) <= limit and decoder.eof and not decoder.unused_data, 'Archive expansion/framing cap'); return value


def ar_members(raw):
    require(raw.startswith(b'!<arch>\n') and len(raw) <= 1048576, 'Bounded Debian ar header')
    offset = 8; result = []
    while offset < len(raw):
        require(len(result) < 3 and offset + 60 <= len(raw), 'Debian ar member count/truncation')
        header = raw[offset:offset + 60]; offset += 60
        require(header[58:] == b'`\n' and re.fullmatch(rb' *\d+ *', header[48:58]), 'Debian ar framing')
        name = header[:16].decode('ascii').strip().removesuffix('/'); size = int(header[48:58])
        require(size <= len(raw) - offset, 'Truncated Debian ar member')
        result.append((name, raw[offset:offset + size])); offset += size
        if size % 2:
            require(raw[offset:offset + 1] == b'\n', 'Debian ar padding'); offset += 1
    require(len(result) == 3 and result[0] == ('debian-binary', b'2.0\n'), 'Debian ar version/order')
    require(re.fullmatch(r'control\.tar\.(gz|xz|zst|bz2)', result[1][0]) and re.fullmatch(r'data\.tar\.(gz|xz|zst|bz2)', result[2][0]), 'Debian control/data order or unsupported compression')
    return result[1:]


def tar_entries(raw):
    entries = {}; total = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            require(len(entries) < 128, 'Runtime archive file count')
            name = member.name.removeprefix('./').rstrip('/')
            if name in ('', '.') and member.isdir(): continue
            parts = PurePosixPath(name)
            require(name and not parts.is_absolute() and not any(p in ('', '.', '..') for p in name.rstrip('/').split('/'))
                and not any(c in name for c in ('\\', ':', '\x00')), 'Runtime archive unsafe path')
            require(name.casefold() not in {p.casefold() for p in entries}, 'Runtime archive duplicate path')
            require(member.isdir() or member.isfile() or member.issym(), 'Runtime archive special/hardlink entry')
            require(0 <= member.size <= 8388608 and total + member.size <= 8388608, 'Runtime archive member expansion')
            if member.isfile():
                stream = archive.extractfile(member); body = stream.read(member.size + 1); stream.close()
                require(len(body) == member.size, 'Truncated runtime tar member'); total += len(body)
            else: body = None
            entries[name.rstrip('/')] = {'kind': 'directory' if member.isdir() else 'file' if member.isfile() else 'symlink',
                'body': body, 'link': member.linkname}
    return entries


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
    require(all(e['kind'] != 'symlink' or p == link for p, e in data.items()), 'Unexpected runtime symlink')
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
