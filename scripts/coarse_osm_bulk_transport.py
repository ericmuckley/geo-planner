"""Direct metered GETs, captured-metadata wheel locks and bounded ZIP validation."""
import hashlib
import http.client
import json
from pathlib import Path, PurePosixPath
import re
import stat
import time
from urllib.parse import urlsplit
import zipfile
from email.parser import BytesParser

from coarse_osm_input import NativeResponse, absolute_timeout
from coarse_osm_records import canonical, strict_json
from coarse_timing_input import digest, json_bytes, require


PACKAGES = {'osmium', 'requests', 'charset-normalizer', 'idna', 'urllib3', 'certifi'}


def endpoint(url):
    p = urlsplit(url)
    require(p.scheme == 'https' and p.hostname in {'download.geofabrik.de', 'pypi.org', 'files.pythonhosted.org'}
        and p.port in (None, 443) and not p.username and not p.password and not p.query and not p.fragment
        and p.path.startswith('/') and not any(c in url for c in ('\\', '\r', '\n')), 'Unlisted TLS endpoint')
    return p


class Https:
    def open(self, url, seconds, idle):
        p = endpoint(url); conn = http.client.HTTPSConnection(p.hostname, 443, timeout=min(seconds, idle))
        try:
            conn.request('GET', p.path, headers={'User-Agent': 'geo-planner-osm-offline/2', 'Accept-Encoding': 'identity', 'Connection': 'close'})
            return NativeResponse(conn, conn.getresponse())
        except BaseException:
            conn.close(); raise


class Meter:
    def __init__(self, root, specs, caps, *, transport=None, clock=time.monotonic, alarm=absolute_timeout):
        self.root = Path(root).resolve(); self.specs, self.caps = specs, caps
        require(self.root.is_dir() and not any(self.root.iterdir()), 'Meter needs new empty output')
        require(len(specs) <= caps['attempts'] and len({s['url'] for s in specs}) == len(specs), 'Duplicate/retry request recipe')
        for s in specs:
            endpoint(s['url']); require(s['kind'] in ('metadata', 'wheel', 'pbf') and s['maxBytes'] > 0, 'Invalid request spec')
        self.transport, self.clock, self.alarm = transport or Https(), clock, alarm
        self.started = clock(); self.events = []; self.body_bytes = 0; self.by_kind = {'metadata': 0, 'wheel': 0, 'pbf': 0}; self.failed = False
        self.checkpoint()

    def checkpoint(self):
        raw = json_bytes({'events': self.events, 'receivedBodyBytes': self.body_bytes, 'bodyBytesByKind': self.by_kind,
            'elapsedSeconds': self.clock() - self.started, 'stopped': self.failed, 'counterScope': 'read1/IncompleteRead.partial delivered payload, excluding headers/TCP/TLS/kernel buffering'})
        require(len(raw) <= 2097152, 'HTTP ledger bound')
        temp = self.root / 'http-ledger.partial'; temp.write_bytes(raw); temp.replace(self.root / 'http-ledger.json')

    def remaining_time(self):
        left = self.caps['wallSeconds'] - (self.clock() - self.started)
        require(left > 0 and not self.failed, 'HTTP run stopped/elapsed cap'); return left

    def fetch(self, number):
        require(number == len(self.events) and number < len(self.specs), 'HTTP recipe order/retry')
        spec = self.specs[number]; seconds = min(spec['seconds'], self.remaining_time())
        require(self.body_bytes < self.caps['totalBytes'], 'Aggregate HTTP body cap')
        event = {'number': number + 1, 'url': spec['url'], 'kind': spec['kind'], 'method': 'GET', 'status': None,
            'bodyFile': f'{number + 1:03d}.bin', 'bodyBytes': 0, 'outcome': 'started', 'absoluteSeconds': seconds,
            'startedElapsed': self.clock() - self.started}
        began = self.clock()
        def within():
            self.remaining_time(); require(self.clock() - began < seconds, 'HTTP absolute elapsed cap')
        path = self.root / event['bodyFile']; response = None; sha, md5 = hashlib.sha256(), hashlib.md5()
        self.events.append(event); self.checkpoint()
        try:
            with path.open('xb', buffering=0) as output:
                def save(chunk):
                    require(isinstance(chunk, bytes), 'Nonbinary transport body')
                    self.body_bytes += len(chunk); self.by_kind[spec['kind']] += len(chunk); event['bodyBytes'] += len(chunk)
                    require(output.write(chunk) == len(chunk), 'Incomplete spool write'); sha.update(chunk); md5.update(chunk); self.checkpoint()
                with self.alarm(seconds):
                    response = self.transport.open(spec['url'], seconds, self.caps['idleSeconds']); within(); event['status'] = response.status
                    read_limit = spec['maxBytes'] if response.status == 200 else min(spec['maxBytes'], self.caps.get('errorBytes', 65536))
                    headers = {}
                    for name, value in response.headers:
                        require(isinstance(value, str) and len(value) <= 4096, 'HTTP header bound')
                        key = name.lower()
                        if key in ('content-length', 'transfer-encoding', 'content-encoding', 'content-type', 'location'):
                            require(key not in headers, 'Duplicate HTTP framing header'); headers[key] = value
                    event['headers'] = headers
                    require(headers.get('content-encoding', 'identity').strip().lower() in ('', 'identity'), 'HTTP compression refused')
                    require(not ('content-length' in headers and 'transfer-encoding' in headers), 'Conflicting HTTP framing')
                    require(headers.get('transfer-encoding', 'chunked').strip().lower() == 'chunked', 'Unsupported transfer framing')
                    length = headers.get('content-length')
                    require(length is None or re.fullmatch(r'\d{1,20}', length), 'Invalid HTTP length')
                    expected = None if length is None else int(length)
                    require(expected is None or expected <= read_limit, 'Declared body oversize')
                    if response.status == 200 and 'exactBytes' in spec: require(expected is None or expected == spec['exactBytes'], 'Declared exact source size drift')
                    while expected is None or event['bodyBytes'] < expected:
                        within()
                        size = min(65536, read_limit + 1 - event['bodyBytes'], self.caps['totalBytes'] - self.body_bytes,
                            self.caps['kindBytes'][spec['kind']] - self.by_kind[spec['kind']],
                            self.caps['workingBytes'] - sum(p.stat().st_size for p in self.root.iterdir() if p.is_file()) - 8388608)
                        require(size > 0, 'HTTP body/kind/storage cap')
                        try: chunk = response.read1(size)
                        except http.client.IncompleteRead as error:
                            require(len(error.partial) <= size, 'Partial read exceeded bound'); save(error.partial); raise ValueError('Truncated HTTP body') from error
                        require(len(chunk) <= size, 'Transport exceeded read bound')
                        if not chunk: break
                        save(chunk); within(); require(event['bodyBytes'] <= read_limit, 'Streamed body oversize')
                    require(expected is None or event['bodyBytes'] == expected, 'Truncated HTTP body')
                    require(response.status == 200, 'HTTP refusal ' + str(response.status))
                    if 'exactBytes' in spec: require(event['bodyBytes'] == spec['exactBytes'], 'Exact source size drift')
                    if 'sha256' in spec: require(sha.hexdigest() == spec['sha256'], 'Downloaded SHA256 drift')
                    if 'md5' in spec: require(md5.hexdigest() == spec['md5'], 'Downloaded publisher checksum drift')
                    response.close(); response = None; within(); event['outcome'] = 'complete'
            return path
        except Exception as error:
            self.failed = True; event.update(outcome='failed', errorType=type(error).__name__, error=str(error)[:1000]); raise
        finally:
            # Failed-response cleanup has its own bounded alarm; it cannot block forever after the request alarm.
            try:
                if response is not None:
                    try:
                        with self.alarm(min(2., max(.001, self.caps['wallSeconds'] - (self.clock() - self.started)))): response.close()
                    except Exception as error:
                        self.failed = True; event.update(outcome='failed', closeError=str(error)[:500])
            finally:
                event.update(bodySha256=sha.hexdigest(), bodyMd5=md5.hexdigest(), finishedElapsed=self.clock() - self.started); self.checkpoint()


def packaging_api():
    # Already in the immutable cached Python/pip image; no app or new package dependency.
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.specifiers import SpecifierSet
    from pip._vendor.packaging.version import Version
    from pip._vendor.packaging.utils import canonicalize_name, parse_wheel_filename
    from pip._vendor.packaging.tags import sys_tags
    from pip._vendor.packaging.markers import default_environment
    return Requirement, SpecifierSet, Version, canonicalize_name, parse_wheel_filename, sys_tags, default_environment


def wheel_lock(metadata, root_pin, *, tags=None, environment=None):
    Req, Spec, Ver, name, parse, sys_tags, env = packaging_api()
    supported = list(sys_tags()) if tags is None else list(tags); target = env() if environment is None else dict(environment); target['extra'] = ''
    require(metadata and len(metadata) <= 6, 'Package closure count')
    values = {}
    for key, data in metadata.items():
        normalized = name(key); require(normalized in PACKAGES and normalized not in values, 'Unexpected/duplicate package')
        require(name(data['info']['name']) == normalized, 'Package metadata identity')
        version = Ver(data['info']['version']); require(not version.is_prerelease and not version.is_devrelease, 'Unstable tool version')
        require(not data['info'].get('requires_python') or Spec(data['info']['requires_python']).contains(target['python_full_version']), 'Unsupported tool Python')
        candidates = []
        for f in data['urls']:
            if f['packagetype'] != 'bdist_wheel' or f.get('yanked'): continue
            n, v, _, wt = parse(f['filename'])
            matches = [i for i, t in enumerate(supported) if t in wt]
            if not matches or n != normalized or v != version: continue
            if f.get('requires_python') and not Spec(f['requires_python']).contains(target['python_full_version']): continue
            p = endpoint(f['url'])
            require(p.hostname == 'files.pythonhosted.org' and p.path.startswith('/packages/') and p.path.endswith('/' + f['filename']), 'Wheel URL/name')
            require(type(f['size']) is int and f['size'] > 0 and re.fullmatch('[a-f0-9]{64}', f['digests']['sha256']), 'Wheel size/digest')
            candidates.append((min(matches), f['filename'], f))
        require(candidates, 'No compatible locked wheel: ' + normalized)
        f = min(candidates)[2]
        if normalized == 'osmium': require(all(f[k] == root_pin['wheel'][k] for k in ('filename', 'size', 'url')) and f['digests']['sha256'] == root_pin['wheelSha256'], 'Root reader pin drift')
        dependencies = []
        for text in data['info'].get('requires_dist') or []:
            req = Req(text)
            if req.marker and not req.marker.evaluate(target): continue
            require(not req.url and not req.extras and name(req.name) in PACKAGES, 'Unsupported tool dependency')
            dependencies.append((name(req.name), str(req.specifier)))
        values[normalized] = {'name': normalized, 'version': str(version), 'filename': f['filename'], 'url': f['url'], 'size': f['size'],
            'sha256': f['digests']['sha256'], 'dependencies': sorted(dependencies), 'metadataSha256': hashlib.sha256(canonical(data)).hexdigest()}
    required = {'osmium'}; pending = ['osmium']
    while pending:
        require(pending[-1] in values, 'Missing tool dependency metadata'); current = values[pending.pop()]
        for n, constraint in current['dependencies']:
            require(n in values and Spec(constraint).contains(values[n]['version']), 'Tool dependency version/closure mismatch')
            if n not in required: required.add(n); pending.append(n)
    require(set(values) == required, 'Unneeded/missing packages in lock')
    require(sum(f['size'] for f in values.values()) <= 134217728, 'Tool archive sum bound')
    return {'packages': sorted(values.values(), key=lambda f: f['name']), 'targetEnvironment': target,
        'supportedTagsSha256': hashlib.sha256(canonical([str(t) for t in supported])).hexdigest(), 'toolArchiveBytes': sum(f['size'] for f in values.values())}


def validate_lock(lock, metadata, root_pin, **target):
    require(canonical(lock) == canonical(wheel_lock(metadata, root_pin, **target)), 'Tool lock/metadata tampering')


def unpack_wheel(archive, pin, root, max_bytes, *, total_files=10000):
    require(Path(archive).stat().st_size == pin['size'] and digest(archive) == pin['sha256'], 'Wheel archive identity')
    root = Path(root).resolve(); root.mkdir()  # Unique per wheel; installed closure merged only by offline pip later.
    written = count = 0; seen = set()
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist(); require(len(infos) <= total_files, 'Wheel file-count cap')
        metadata = [f for f in infos if f.filename.endswith('.dist-info/METADATA')]
        require(len(metadata) == 1 and metadata[0].file_size <= 1048576, 'Wheel METADATA bound')
        info = BytesParser().parsebytes(zipped.read(metadata[0]))
        name = packaging_api()[3]
        require(name(info['Name']) == name(pin['name']) and info['Version'] == pin['version'], 'Wheel metadata name/version drift')
        for member in infos:
            rel = PurePosixPath(member.filename); mode = member.external_attr >> 16
            require(member.filename and not rel.is_absolute() and not any(p in ('', '..', '.') for p in member.filename.rstrip('/').split('/'))
                and not any(c in member.filename for c in ('\\', ':', '\x00')) and member.filename.casefold() not in seen, 'Unsafe/duplicate wheel path')
            require(not stat.S_ISLNK(mode) and (stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)) and not member.flag_bits & 1, 'Wheel symlink/special/encrypted entry')
            require(not member.filename.endswith('.pth') and member.file_size >= 0, 'Wheel executable path hook')
            seen.add(member.filename.casefold()); dest = root.joinpath(*rel.parts)
            require(dest.is_relative_to(root), 'Wheel path escape')
            if member.is_dir(): dest.mkdir(parents=True, exist_ok=True); continue
            require(written + member.file_size <= max_bytes, 'Installed tool-byte cap')
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(member) as source, dest.open('xb') as output:
                received = 0
                while True:
                    raw = source.read(min(65536, member.file_size + 1 - received))
                    if not raw: break
                    received += len(raw)
                    require(received <= member.file_size and written + len(raw) <= max_bytes, 'Wheel inflation bound')
                    output.write(raw); written += len(raw)
                require(received == member.file_size, 'Truncated wheel member')
            count += 1
    return {'installedBytes': written, 'files': count}
