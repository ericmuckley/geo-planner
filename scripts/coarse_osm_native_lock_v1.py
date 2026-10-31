"""Finite public OCI/Git metadata lock. Never downloads layers or source blobs."""
import hashlib
import http.client
from pathlib import Path, PurePosixPath
import re
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from coarse_osm_input import NativeResponse, absolute_timeout
from coarse_osm_records import strict_json
from coarse_timing_input import json_bytes, require

REPOSITORY = 'pypa/manylinux_2_28_aarch64'
SOURCES = [('osmcode/libosmium', 'v2.23.1'), ('mapbox/protozero', 'v1.8.2')]
ROOT_URL = 'https://quay.io/v2/' + REPOSITORY + '/manifests/latest'
SCOPE = 'repository:' + REPOSITORY + ':pull'
INDEX_TYPES = {'application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json'}
MANIFEST_TYPES = {'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'}
CONFIG_TYPES = {'application/vnd.oci.image.config.v1+json', 'application/vnd.docker.container.image.v1+json'}
LAYER_TYPES = {'application/vnd.oci.image.layer.v1.tar', 'application/vnd.oci.image.layer.v1.tar+gzip',
    'application/vnd.oci.image.layer.v1.tar+zstd', 'application/vnd.docker.image.rootfs.diff.tar.gzip'}
CAPS = {'attempts': 16, 'eachBytes': 2097152, 'totalBytes': 16777216, 'requestSeconds': 30,
    'idleSeconds': 15, 'workerSeconds': 540, 'hostSeconds': 600, 'hostWorkSeconds': 570,
    'workingBytes': 1073741824, 'tmpBytes': 268435456, 'fileBytes': 67108864,
    'reportBytes': 2097152, 'treeEntries': 20000, 'tagDepth': 2}


def save(path, value):
    raw = json_bytes(value)
    require(len(raw) <= CAPS['reportBytes'] and not path.exists(), 'Native lock report cap/reuse')
    path.write_bytes(raw)


def hash_id(value, size=64):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(size) + '}', value), 'Invalid metadata hash')
    return value


def image_digest(value):
    require(isinstance(value, str) and value.startswith('sha256:'), 'Unsupported OCI digest')
    hash_id(value[7:])
    return value


def endpoint(url, kind):
    p = urlsplit(url)
    require(p.scheme == 'https' and p.port in (None, 443) and p.netloc == p.hostname
        and not p.username and not p.password and not p.fragment and not any(c in url for c in ('\\', '\r', '\n')), 'Unlisted metadata endpoint')
    if kind == 'auth':
        require(p.hostname == 'quay.io' and p.path == '/v2/auth' and parse_qs(p.query) == {'service': ['quay.io'], 'scope': [SCOPE]}, 'Unlisted registry auth scope')
    elif kind == 'registry':
        require(p.hostname == 'quay.io' and not p.query and re.fullmatch('/v2/' + REPOSITORY + r'/manifests/(latest|sha256:[0-9a-f]{64})', p.path), 'Unlisted registry manifest')
    elif kind == 'config':
        require(p.hostname == 'quay.io' and not p.query and re.fullmatch('/v2/' + REPOSITORY + r'/blobs/sha256:[0-9a-f]{64}', p.path), 'Unlisted registry config')
    else:
        require(kind == 'git' and p.hostname == 'api.github.com', 'Unlisted metadata kind/host')
        allowed = False
        for repo, tag in SOURCES:
            prefix = '/repos/' + repo + '/git/'
            allowed |= p.path == prefix + 'ref/tags/' + tag and not p.query
            allowed |= bool(re.fullmatch(re.escape(prefix) + '(tags|commits)/[0-9a-f]{40}', p.path)) and not p.query
            allowed |= bool(re.fullmatch(re.escape(prefix) + 'trees/[0-9a-f]{40}', p.path)) and p.query == 'recursive=1'
        require(allowed, 'Unlisted Git metadata path')
    return p


class Https:
    def open(self, url, kind, headers, seconds):
        p = endpoint(url, kind)
        connection = http.client.HTTPSConnection(p.hostname, 443, timeout=min(seconds, CAPS['idleSeconds']))
        try:
            connection.request('GET', p.path + ('?' + p.query if p.query else ''), headers={
                'User-Agent': 'geo-planner-native-lock/1', 'Accept-Encoding': 'identity', 'Connection': 'close', **headers})
            return NativeResponse(connection, connection.getresponse())
        except BaseException:
            connection.close()
            raise


class Metadata:
    def __init__(self, root, *, transport=None, clock=time.monotonic, alarm=absolute_timeout, caps=CAPS):
        self.root = Path(root)
        self.root.mkdir()
        self.transport, self.clock, self.alarm, self.caps = transport or Https(), clock, alarm, caps
        self.started = clock()
        self.events, self.bytes = [], 0
        self.stopped = False
        self.checkpoint()

    def check(self):
        require(not self.stopped and self.clock() - self.started < self.caps['workerSeconds'], 'Metadata stopped/deadline')
        require(sum(p.stat().st_size for p in self.root.iterdir() if p.is_file()) < self.caps['workingBytes'] - self.caps['tmpBytes'] - 8388608, 'Metadata storage cap')

    def checkpoint(self):
        raw = json_bytes({'events': self.events, 'receivedBodyBytes': self.bytes, 'stopped': self.stopped,
            'elapsedSeconds': self.clock() - self.started, 'counterScope': 'read1/IncompleteRead.partial payload only; excludes headers/socket/TLS buffering. Auth body is hashed/counted but never persisted.'})
        require(len(raw) <= self.caps['reportBytes'], 'Metadata ledger cap')
        partial = self.root / 'ledger.partial'
        require(not partial.is_symlink(), 'Metadata ledger symlink')
        partial.write_bytes(raw)
        partial.replace(self.root / 'ledger.json')

    def fetch(self, url, kind, *, bearer=None):
        endpoint(url, kind)
        self.check()
        require(len(self.events) < self.caps['attempts'] and self.bytes < self.caps['totalBytes'], 'Metadata attempt/body cap')
        require(bearer is None or kind in ('registry', 'config'), 'Refuse cross-host auth')
        event = {'number': len(self.events) + 1, 'url': url, 'kind': kind, 'status': None, 'bodyBytes': 0,
            'bodyFile': None if kind == 'auth' else f'{len(self.events) + 1:03d}.bin', 'outcome': 'started'}
        self.events.append(event)
        self.checkpoint()
        response = stream = None
        hashed, body = hashlib.sha256(), bytearray()
        headers = {'Accept': ', '.join(sorted(INDEX_TYPES | MANIFEST_TYPES)) if kind == 'registry' else 'application/json'}
        if kind == 'git':
            headers.update(Accept='application/vnd.github+json', **{'X-GitHub-Api-Version': '2026-03-10'})
        if bearer is not None:
            headers['Authorization'] = 'Bearer ' + bearer
        seconds = min(self.caps['requestSeconds'], self.caps['workerSeconds'] - (self.clock() - self.started))
        def receive(chunk):
            require(isinstance(chunk, bytes), 'Nonbinary metadata body')
            self.bytes += len(chunk)
            event['bodyBytes'] += len(chunk)
            hashed.update(chunk)
            body.extend(chunk)
            if stream is not None:
                stream.write(chunk)
            self.checkpoint()
        try:
            if event['bodyFile'] is not None:
                stream = (self.root / event['bodyFile']).open('xb', buffering=0)
            with self.alarm(seconds):
                response = self.transport.open(url, kind, headers, seconds)
                event['status'] = response.status
                selected = {}
                for key, value in response.headers:
                    require(isinstance(value, str) and len(value) <= 4096, 'Metadata header bound')
                    key = key.lower()
                    if key in ('content-length', 'transfer-encoding', 'content-encoding', 'content-type', 'location', 'docker-content-digest', 'www-authenticate', 'x-ratelimit-remaining', 'x-ratelimit-reset'):
                        require(key not in selected, 'Duplicate metadata header')
                        selected[key] = value
                event['headers'] = selected
                require(selected.get('content-encoding', 'identity').lower() in ('identity', ''), 'Encoded metadata refused')
                require(not ('content-length' in selected and 'transfer-encoding' in selected), 'Conflicting metadata framing')
                require(selected.get('transfer-encoding', 'chunked').lower() == 'chunked', 'Unsupported metadata framing')
                length = selected.get('content-length')
                require(length is None or re.fullmatch(r'[0-9]{1,20}', length), 'Invalid metadata length')
                expected = None if length is None else int(length)
                allowance = min(self.caps['eachBytes'], self.caps['totalBytes'] - self.bytes)
                require(expected is None or expected <= allowance, 'Declared metadata body cap')
                while expected is None or event['bodyBytes'] < expected:
                    self.check()
                    size = min(65536, allowance - event['bodyBytes'])
                    require(size > 0, 'Metadata quota exhausted before known EOF')
                    try:
                        chunk = response.read1(size)
                    except http.client.IncompleteRead as error:
                        require(len(error.partial) <= size, 'Metadata partial read bound')
                        receive(error.partial)
                        raise ValueError('Truncated metadata body') from None
                    require(len(chunk) <= size, 'Metadata transport read bound')
                    if not chunk:
                        break
                    receive(chunk)
                require(expected is None or event['bodyBytes'] == expected, 'Truncated metadata body')
                event['outcome'] = 'body_complete'
            return bytes(body), response.status, selected
        except Exception as error:
            self.stopped = True
            event.update(outcome='stopped', errorType=type(error).__name__, error=str(error)[:512])
            raise
        finally:
            if stream is not None:
                stream.close()
            try:
                if response is not None:
                    with self.alarm(2):
                        response.close()
            except Exception:
                self.stopped = True
                event.update(outcome='stopped', closeError='Response close failed')
                raise
            finally:
                event['bodySha256'] = hashed.hexdigest()
                event['authBodyRedacted'] = kind == 'auth'
                self.checkpoint()


def descriptor(row, media_types):
    require(isinstance(row, dict) and row.get('mediaType') in media_types, 'Unsupported OCI descriptor type')
    image_digest(row.get('digest'))
    require(type(row.get('size')) is int and 0 < row['size'] <= 2147483648, 'OCI descriptor size')
    return {k: row[k] for k in ('mediaType', 'digest', 'size')}


def auth_url(challenge):
    require(isinstance(challenge, str) and challenge.startswith('Bearer '), 'Unsupported registry challenge')
    fields = re.findall(r'([a-z]+)="([^"\r\n]*)"', challenge[7:])
    require(len(fields) in (2, 3) and len(dict(fields)) == len(fields), 'Invalid registry challenge')
    values = dict(fields)
    require(set(values) in ({'realm', 'service'}, {'realm', 'service', 'scope'})
        and values['realm'] == 'https://quay.io/v2/auth' and values['service'] == 'quay.io' and values.get('scope', SCOPE) == SCOPE, 'Unlisted registry challenge scope')
    require(re.sub(r'[a-z]+="[^"\r\n]*"', '', challenge[7:]).replace(',', '').strip() == '', 'Invalid registry challenge syntax')
    return values['realm'] + '?' + urlencode({'service': values['service'], 'scope': SCOPE})


def lock_image(meter):
    bearer = None
    raw, status, headers = meter.fetch(ROOT_URL, 'registry')
    if status == 401:
        token_body, token_status, _ = meter.fetch(auth_url(headers.get('www-authenticate')), 'auth')
        require(token_status == 200, 'Registry anonymous auth refused')
        value = strict_json(token_body)
        bearer = value.get('token', value.get('access_token'))
        require(isinstance(bearer, str) and re.fullmatch(r'[A-Za-z0-9._~+/-]{8,32768}={0,2}', bearer), 'Invalid anonymous bearer')
        require('token' not in value or 'access_token' not in value or value['token'] == value['access_token'], 'Conflicting anonymous bearer')
        raw, status, headers = meter.fetch(ROOT_URL, 'registry', bearer=bearer)
    require(status == 200, 'Registry HTTP refusal ' + str(status))
    root_digest = image_digest(headers.get('docker-content-digest'))
    require('sha256:' + hashlib.sha256(raw).hexdigest() == root_digest, 'Root registry digest mismatch')
    root = strict_json(raw)
    media = root.get('mediaType')
    selected_digest = root_digest
    if media in INDEX_TYPES:
        require(root.get('schemaVersion') == 2 and isinstance(root.get('manifests'), list) and len(root['manifests']) <= 128, 'OCI index schema/count')
        choices = []
        for row in root['manifests']:
            desc = descriptor(row, MANIFEST_TYPES)
            platform = row.get('platform', {})
            if platform.get('os') == 'linux' and platform.get('architecture') == 'arm64' and platform.get('variant') in (None, 'v8'):
                choices.append(desc)
        require(len(choices) == 1, 'Missing/ambiguous arm64 image')
        selected = choices[0]
        require(selected['size'] <= CAPS['eachBytes'], 'Selected image manifest body cap')
        selected_digest = selected['digest']
        raw, status, headers = meter.fetch('https://quay.io/v2/' + REPOSITORY + '/manifests/' + selected_digest, 'registry', bearer=bearer)
        require(status == 200 and len(raw) == selected['size'] and 'sha256:' + hashlib.sha256(raw).hexdigest() == selected_digest, 'Selected manifest status/size/digest')
        require('docker-content-digest' not in headers or headers['docker-content-digest'] == selected_digest, 'Selected manifest header digest')
        root = strict_json(raw)
    require(root.get('schemaVersion') == 2 and root.get('mediaType') in MANIFEST_TYPES, 'OCI image manifest schema')
    config = descriptor(root.get('config'), CONFIG_TYPES)
    require(config['size'] <= CAPS['eachBytes'], 'OCI config body cap')
    require(isinstance(root.get('layers'), list) and 0 < len(root['layers']) <= 256, 'OCI layer count')
    layers = [descriptor(row, LAYER_TYPES) for row in root['layers']]
    require(config['digest'] not in {r['digest'] for r in layers}, 'OCI config/layer collision')
    require(sum(r['size'] for r in layers) + config['size'] <= 2147483648, 'Compressed builder closure exceeds2GiB')
    body, status, _ = meter.fetch('https://quay.io/v2/' + REPOSITORY + '/blobs/' + config['digest'], 'config', bearer=bearer)
    require(status == 200 and len(body) == config['size'] and 'sha256:' + hashlib.sha256(body).hexdigest() == config['digest'], 'Config status/size/digest')
    info = strict_json(body)
    require(info.get('os') == 'linux' and info.get('architecture') == 'arm64' and info.get('variant') in (None, 'v8'), 'Image config platform')
    fs = info.get('rootfs', {})
    require(fs.get('type') == 'layers' and isinstance(fs.get('diff_ids'), list) and len(fs['diff_ids']) == len(layers), 'OCI rootfs layer count')
    for value in fs['diff_ids']:
        image_digest(value)
    return {'repository': 'quay.io/' + REPOSITORY, 'selector': 'latest', 'rootDigest': root_digest,
        'manifestDigest': selected_digest, 'config': config, 'layers': layers, 'diffIds': fs['diff_ids'],
        'compressedLayerBytes': sum(r['size'] for r in layers), 'platform': 'linux/arm64', 'expandedBytes': None,
        'binaryAcquired': False, 'compilerOrAbiQualified': False}


def git_json(meter, repo, suffix):
    body, status, _ = meter.fetch('https://api.github.com/repos/' + repo + '/git/' + suffix, 'git')
    require(status == 200, 'Git metadata HTTP refusal ' + str(status))
    value = strict_json(body)
    require(isinstance(value, dict), 'Invalid Git metadata schema')
    return value


def lock_source(meter, repo, tag):
    ref = git_json(meter, repo, 'ref/tags/' + tag)
    require(ref.get('ref') == 'refs/tags/' + tag, 'Git ref mismatch')
    obj, seen, tags = ref.get('object', {}), set(), []
    while obj.get('type') == 'tag':
        identity = hash_id(obj.get('sha'), 40)
        require(identity not in seen and len(tags) < CAPS['tagDepth'], 'Git annotated-tag depth/cycle')
        seen.add(identity)
        annotated = git_json(meter, repo, 'tags/' + identity)
        require(annotated.get('sha') == identity, 'Annotated tag identity')
        tags.append(identity)
        obj = annotated.get('object', {})
    require(obj.get('type') == 'commit', 'Git tag does not resolve to commit')
    commit = hash_id(obj.get('sha'), 40)
    value = git_json(meter, repo, 'commits/' + commit)
    require(value.get('sha') == commit, 'Git commit identity')
    tree_id = hash_id(value.get('tree', {}).get('sha'), 40)
    tree = git_json(meter, repo, 'trees/' + tree_id + '?recursive=1')
    require(tree.get('sha') == tree_id and tree.get('truncated') is False, 'Git tree identity/truncation')
    entries = tree.get('tree')
    require(isinstance(entries, list) and 0 < len(entries) <= CAPS['treeEntries'], 'Git tree count')
    rows, paths = [], set()
    for row in entries:
        path = row.get('path')
        require(isinstance(path, str) and 0 < len(path.encode()) <= 4096 and not any(ord(c) < 32 for c in path)
            and '\\' not in path and not path.startswith('/') and all(p not in ('', '.', '..') for p in path.split('/'))
            and str(PurePosixPath(path)) == path and path not in paths, 'Unsafe/duplicate Git path')
        paths.add(path)
        identity = hash_id(row.get('sha'), 40)
        mode, kind = row.get('mode'), row.get('type')
        require((mode, kind) in {('040000', 'tree'), ('160000', 'commit'), ('100644', 'blob'), ('100755', 'blob'), ('120000', 'blob')}, 'Git tree mode/type')
        item = {'path': path, 'mode': mode, 'type': kind, 'sha': identity}
        if kind == 'blob':
            require(type(row.get('size')) is int and 0 <= row['size'] <= 1073741824, 'Git blob size')
            item['size'] = row['size']
        rows.append(item)
    prefix = 'include/osmium/' if repo == SOURCES[0][0] else 'include/protozero/'
    kinds = {r['path']: r['type'] for r in rows}
    for path in paths:
        require(all(kinds.get(str(parent)) == 'tree' for parent in PurePosixPath(path).parents if str(parent) != '.'), 'Git tree parent/type mismatch')
    selected = [r for r in rows if r['type'] != 'tree' and (r['path'].startswith(prefix) or r['path'] in ('LICENSE', 'LICENSE.txt', 'LICENSE.md', 'COPYING'))]
    require(any(r['path'].startswith(prefix) for r in selected) and any('/' not in r['path'] for r in selected), 'Source header/license closure absent')
    require(all(r['type'] == 'blob' and r['mode'] in ('100644', '100755') for r in selected), 'Selected source symlink/submodule refused')
    require(sum(r['size'] for r in selected) <= 1073741824, 'Selected source tree cap')
    return {'repository': repo, 'tagSelector': tag, 'annotatedTags': tags, 'commit': commit, 'tree': tree_id,
        'entries': sorted(rows, key=lambda r: r['path']), 'selectedFiles': sorted(selected, key=lambda r: r['path']),
        'selectedBytes': sum(r['size'] for r in selected), 'archiveSha256': None, 'sourceAcquired': False,
        'scope': 'Git API object identities only; file contents/archive SHA256 and compilation remain unverified.'}


def resolve(root, *, transport=None, clock=time.monotonic, alarm=absolute_timeout, caps=CAPS):
    root = Path(root)
    meter = Metadata(root / 'http', transport=transport, clock=clock, alarm=alarm, caps=caps)
    progress = {'image': 'unmeasured', 'sources': {repo: 'unmeasured' for repo, _ in SOURCES},
        'binaryDownloads': 0, 'sourceOrSampleReads': 0, 'modelChanged': False}
    began = clock()
    try:
        image = lock_image(meter)
        save(root / 'image-lock.json', image)
        progress['image'] = 'metadata_locked'
        sources = []
        for index, (repo, tag) in enumerate(SOURCES):
            value = lock_source(meter, repo, tag)
            save(root / f'source-{index + 1}-lock.json', value)
            sources.append(value)
            progress['sources'][repo] = 'metadata_locked'
        save(root / 'lock.json', {'image': image, 'sources': sources, 'metadataOnly': True,
            'expandedImageBytes': None, 'buildOrAbiQualified': False, 'fullImportAdmitted': False})
        progress['status'] = 'metadata_locked_not_acquired'
        return 0
    except Exception as error:
        meter.stopped = True
        progress.update(status='stopped', errorType=type(error).__name__, error=str(error)[:1000])
        return 2
    finally:
        progress.update(requests=len(meter.events), receivedBodyBytes=meter.bytes, resolveSecondsBeforeSummary=clock() - began)
        meter.checkpoint()
        save(root / 'result.json', progress)


def verify_saved(root):
    """Offline reconciliation, with a synthetic auth placeholder (never a token replay)."""
    import tempfile
    import io
    root = Path(root)
    ledger = strict_json((root / 'http/ledger.json').read_bytes())
    require(sum(e['bodyBytes'] for e in ledger['events']) == ledger['receivedBodyBytes'], 'Saved ledger byte sum')
    require(len(ledger['events']) <= CAPS['attempts'] and ledger['receivedBodyBytes'] <= CAPS['totalBytes'], 'Saved metadata quotas')
    for event in ledger['events']:
        require(event['bodyBytes'] <= CAPS['eachBytes'], 'Saved individual metadata quota')
        if event['kind'] == 'auth':
            require(event['bodyFile'] is None and event['authBodyRedacted'], 'Auth body must remain redacted')
        else:
            path = root / 'http' / event['bodyFile']
            require(path.stat().st_size == event['bodyBytes'] and hashlib.sha256(path.read_bytes()).hexdigest() == event['bodySha256'], 'Saved public metadata identity')
    state = strict_json((root / 'result.json').read_bytes())
    if state['status'] != 'metadata_locked_not_acquired':
        return {'ledgerVerified': True, 'completeLockReplayed': False, 'scope': 'Preserved stop; no fabricated missing responses.'}
    class Replay:
        def __init__(self): self.index = 0
        def open(self, url, kind, headers, seconds):
            event = ledger['events'][self.index]
            self.index += 1
            require((url, kind) == (event['url'], event['kind']), 'Saved metadata state-machine drift')
            response_headers = dict(event['headers'])
            if kind == 'auth':
                body = json_bytes({'token': 'redacted-placeholder'})
                response_headers.pop('transfer-encoding', None)
                response_headers['content-length'] = str(len(body))
            else:
                body = (root / 'http' / event['bodyFile']).read_bytes()
            class Response:
                status = event['status']
                headers = list(response_headers.items())
                stream = io.BytesIO(body)
                def read1(self, size): return self.stream.read(size)
                def close(self): self.stream.close()
            return Response()
    replay = Replay()
    with tempfile.TemporaryDirectory() as temp:
        require(resolve(Path(temp), transport=replay) == 0 and replay.index == len(ledger['events']), 'Offline metadata lock replay')
        require((Path(temp) / 'lock.json').read_bytes() == (root / 'lock.json').read_bytes(), 'Offline lock differs')
    return {'ledgerVerified': True, 'completeLockReplayed': True, 'scope': 'Public saved JSON replay only; auth placeholder proves neither original token value nor credentials. No network.'}
