"""Config-only CDN correction using a saved manifest; metadata only, no retries."""
import hashlib
import http.client
import io
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

import coarse_osm_native_lock_v1 as v1
from coarse_osm_input import NativeResponse, absolute_timeout
from coarse_osm_records import strict_json
from coarse_timing_input import PilotError, json_bytes, require

CAPS = dict(v1.CAPS, attempts=12, totalBytes=14680064)
MANIFEST_PATH = 'data/coarse-quality/us-osm-native-lock-v1/acquire/http/001.bin'
MANIFEST_SHA = 'a3e02308c822fb6ce0d12248b0c941817ba5e1a1bc9e7bb5929f29c50eaa40a9'
MANIFEST_BYTES = 5542
QUERY_KEYS = sorted(['X-Amz-Algorithm', 'X-Amz-Credential', 'X-Amz-Date', 'X-Amz-Expires',
    'X-Amz-Signature', 'X-Amz-SignedHeaders', 'akamai_signature', 'namespace', 'region', 'repo_name'])


def manifest_info(raw, expected=MANIFEST_SHA):
    require(len(raw) <= CAPS['eachBytes'] and hashlib.sha256(raw).hexdigest() == expected, 'Saved manifest hash/size')
    root = strict_json(raw)
    require(root.get('schemaVersion') == 2 and root.get('mediaType') in v1.MANIFEST_TYPES, 'Saved manifest schema')
    config = v1.descriptor(root.get('config'), v1.CONFIG_TYPES)
    require(config['size'] <= CAPS['eachBytes'], 'Saved config cap')
    require(isinstance(root.get('layers'), list) and 0 < len(root['layers']) <= 256, 'Saved layer count')
    layers = [v1.descriptor(row, v1.LAYER_TYPES) for row in root['layers']]
    require(config['digest'] not in {r['digest'] for r in layers}, 'Saved config/layer collision')
    require(sum(r['size'] for r in layers) + config['size'] <= 2147483648, 'Compressed closure exceeds2GiB')
    return config, layers


def config_url(config):
    return 'https://quay.io/v2/' + v1.REPOSITORY + '/blobs/' + config['digest']


def cdn_path(config):
    identity = v1.image_digest(config['digest'])[7:]
    return '/quayio-production-s3/sha256/' + identity[:2] + '/' + identity


def endpoint(url, kind, config):
    require(isinstance(url, str) and 0 < len(url) <= 4096 and all(33 <= ord(c) <= 126 for c in url)
        and '\\' not in url and '#' not in url, 'Invalid config URI syntax')
    try:
        p = urlsplit(url)
    except ValueError:
        raise PilotError('Invalid config URI syntax') from None
    if kind == 'config':
        require(url == config_url(config), 'Unlisted config endpoint')
    else:
        require(kind == 'cdn' and p.scheme == 'https' and p.netloc == 'cdn01.quay.io'
            and p.path == cdn_path(config), 'Unlisted config CDN endpoint')
        require(not re.search(r'%(?![0-9a-fA-F]{2})', p.query), 'Invalid config query encoding')
        try:
            fields = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True, encoding='utf-8', errors='strict')
        except (ValueError, UnicodeError):
            raise PilotError('Invalid config query syntax') from None
        require(sorted(k for k, _ in fields) == QUERY_KEYS and len(fields) == len(QUERY_KEYS), 'Unlisted config query keys')
        require(all(v and len(v) <= 2048 and all(33 <= ord(c) <= 126 for c in v) for _, v in fields), 'Invalid config query value')
    return p


def public_uri(url, kind, config):
    p = endpoint(url, kind, config)
    return {'scheme': p.scheme, 'host': p.hostname, 'path': p.path,
        'queryParameterNames': QUERY_KEYS if kind == 'cdn' else [],
        'urlBytes': len(url.encode()), 'urlSha256': hashlib.sha256(url.encode()).hexdigest(),
        'queryValuesRedacted': True}


class Https:
    def __init__(self, config): self.config = config

    def open(self, url, kind, headers, seconds):
        require(not any(k.lower() in ('authorization', 'cookie') for k in headers), 'No metadata credentials')
        if kind == 'git':
            return v1.Https().open(url, kind, headers, seconds)
        p = endpoint(url, kind, self.config)
        connection = http.client.HTTPSConnection(p.hostname, 443, timeout=min(seconds, CAPS['idleSeconds']))
        try:
            connection.request('GET', p.path + ('?' + p.query if p.query else ''), headers={
                'User-Agent': 'geo-planner-native-lock/2', 'Accept-Encoding': 'identity', 'Connection': 'close', **headers})
            return NativeResponse(connection, connection.getresponse())
        except BaseException:
            connection.close()
            raise PilotError('Config connection failed; private URI omitted') from None


class Metadata(v1.Metadata):
    def __init__(self, root, config, *, transport=None, caps=CAPS, **kwargs):
        self.config = config
        super().__init__(root, transport=transport or Https(config), caps=caps, **kwargs)

    def checkpoint(self):
        # No redirect/error body or signed Location is ever written, including partial reads.
        raw = json_bytes({'events': self.events, 'receivedBodyBytes': self.bytes, 'stopped': self.stopped,
            'elapsedSeconds': self.clock() - self.started,
            'counterScope': 'read1/IncompleteRead.partial payload only; excludes headers/socket/TLS buffering. Config redirect/error bodies and signed query values are counted/hashed, never persisted.'})
        require(len(raw) <= self.caps['reportBytes'], 'Metadata ledger cap')
        partial = self.root / 'ledger.partial'
        require(not partial.is_symlink(), 'Metadata ledger symlink')
        partial.write_bytes(raw)
        partial.replace(self.root / 'ledger.json')

    def fetch(self, url, kind, *, bearer=None):
        require(bearer is None, 'No V2 auth exchange/forwarding')
        if kind == 'git':
            return super().fetch(url, kind)
        public = public_uri(url, kind, self.config)
        self.check()
        require(len(self.events) < self.caps['attempts'] and self.bytes < self.caps['totalBytes'], 'Metadata attempt/body cap')
        event = {'number': len(self.events) + 1, 'url': public['scheme'] + '://' + public['host'] + public['path'],
            'requestUri': public, 'kind': kind, 'status': None, 'bodyBytes': 0, 'bodyFile': None, 'outcome': 'started'}
        self.events.append(event)
        self.checkpoint()
        response = None
        hashed, body = hashlib.sha256(), bytearray()
        selected, location = {}, None
        stage = 'connection'
        seconds = min(self.caps['requestSeconds'], self.caps['workerSeconds'] - (self.clock() - self.started))
        def receive(chunk):
            require(isinstance(chunk, bytes), 'Nonbinary metadata body')
            self.bytes += len(chunk)
            event['bodyBytes'] += len(chunk)
            hashed.update(chunk)
            body.extend(chunk)
            self.checkpoint()
        try:
            with self.alarm(seconds):
                response = self.transport.open(url, kind, {'Accept': 'application/json'}, seconds)
                require(type(response.status) is int and 100 <= response.status <= 599, 'Invalid metadata status')
                event['status'] = response.status
                stage = 'headers'
                seen = set()
                for key, value in response.headers:
                    require(isinstance(key, str) and isinstance(value, str) and len(value) <= 4096, 'Metadata header bound')
                    key = key.lower()
                    if key not in ('content-length', 'transfer-encoding', 'content-encoding', 'location'):
                        continue
                    require(key not in seen, 'Duplicate metadata header')
                    seen.add(key)
                    if key == 'location':
                        location = value
                        receipt = {'urlBytes': len(value.encode()), 'urlSha256': hashlib.sha256(value.encode()).hexdigest(), 'queryValuesRedacted': True}
                        event['redirectReceipt'] = receipt
                        # Validate before storing even the public host/path/key names.
                        event['redirectReceipt'] = public_uri(value, 'cdn', self.config)
                    else:
                        if key == 'content-length':
                            require(re.fullmatch(r'[0-9]{1,20}', value), 'Invalid metadata length')
                        elif key == 'transfer-encoding':
                            require(value.lower() == 'chunked', 'Unsupported metadata framing')
                        else:
                            require(value.lower() in ('identity', ''), 'Encoded metadata refused')
                        selected[key] = value
                event['headers'] = selected
                require(not ('content-length' in selected and 'transfer-encoding' in selected), 'Conflicting metadata framing')
                expected = int(selected['content-length']) if 'content-length' in selected else None
                allowance = min(self.caps['eachBytes'], self.caps['totalBytes'] - self.bytes)
                require(expected is None or expected <= allowance, 'Declared metadata body cap')
                stage = 'body'
                while expected is None or event['bodyBytes'] < expected:
                    self.check()
                    size = min(65536, allowance - event['bodyBytes'])
                    require(size > 0, 'Metadata quota exhausted before known EOF')
                    try:
                        chunk = response.read1(size)
                    except http.client.IncompleteRead as error:
                        require(len(error.partial) <= size, 'Metadata partial read bound')
                        receive(error.partial)
                        raise PilotError('Truncated config body') from None
                    require(len(chunk) <= size, 'Metadata transport read bound')
                    if not chunk: break
                    receive(chunk)
                require(expected is None or event['bodyBytes'] == expected, 'Truncated metadata body')
                stage = 'config_identity'
                if response.status == 200:
                    require(len(body) == self.config['size'] and 'sha256:' + hashed.hexdigest() == self.config['digest'], 'Config size/digest')
                    event['bodyFile'] = f'{event["number"]:03d}.bin'
                    (self.root / event['bodyFile']).write_bytes(body)
                event['outcome'] = 'body_complete'
            return bytes(body), response.status, location
        except Exception as error:
            self.stopped = True
            event.update(outcome='stopped', errorType=type(error).__name__, stopStage=stage, error='Config response refused; private details omitted')
            raise PilotError('Config response refused; private details omitted') from None
        finally:
            try:
                if response is not None:
                    with self.alarm(2): response.close()
            except Exception:
                self.stopped = True
                event.update(outcome='stopped', closeError='Config close failed; private details omitted')
                raise PilotError('Config close failed; private details omitted') from None
            finally:
                event['bodySha256'] = hashed.hexdigest()
                event['privateBodyRedacted'] = event['bodyFile'] is None
                self.checkpoint()


def lock_image(meter, manifest_raw, manifest_sha=MANIFEST_SHA):
    config, layers = manifest_info(manifest_raw, manifest_sha)
    require(config == meter.config, 'Config binding drift')
    body, status, location = meter.fetch(config_url(config), 'config')
    if status == 302:
        require(location is not None, 'Config redirect missing')
        body, status, _ = meter.fetch(location, 'cdn')
    require(status == 200, 'Config HTTP refusal; no additional redirect/auth/retry')
    info = strict_json(body)
    require(info.get('os') == 'linux' and info.get('architecture') == 'arm64' and info.get('variant') in (None, 'v8'), 'Image config platform')
    fs = info.get('rootfs', {})
    require(fs.get('type') == 'layers' and isinstance(fs.get('diff_ids'), list) and len(fs['diff_ids']) == len(layers), 'OCI rootfs layer count')
    for value in fs['diff_ids']: v1.image_digest(value)
    return {'repository': 'quay.io/' + v1.REPOSITORY, 'selector': 'saved_verified_v1_manifest',
        'rootDigest': 'sha256:' + manifest_sha, 'manifestDigest': 'sha256:' + manifest_sha, 'config': config,
        'layers': layers, 'diffIds': fs['diff_ids'], 'compressedLayerBytes': sum(r['size'] for r in layers),
        'platform': 'linux/arm64', 'expandedBytes': None, 'binaryAcquired': False, 'compilerOrAbiQualified': False}


def resolve(root, manifest, *, manifest_sha=MANIFEST_SHA, transport=None, clock=time.monotonic, alarm=absolute_timeout, caps=CAPS):
    root = Path(root)
    raw = Path(manifest).read_bytes()
    config, _ = manifest_info(raw, manifest_sha)  # No requests before the pinned manifest checks.
    meter = Metadata(root / 'http', config, transport=transport, clock=clock, alarm=alarm, caps=caps)
    progress = {'image': 'unmeasured', 'sources': {repo: 'unmeasured' for repo, _ in v1.SOURCES},
        'binaryDownloads': 0, 'sourceOrSampleReads': 0, 'modelChanged': False}
    began = clock()
    try:
        image = lock_image(meter, raw, manifest_sha)
        v1.save(root / 'image-lock.json', image)
        progress['image'] = 'metadata_locked'
        sources = []
        for index, (repo, tag) in enumerate(v1.SOURCES):
            value = v1.lock_source(meter, repo, tag)
            v1.save(root / f'source-{index + 1}-lock.json', value)
            sources.append(value)
            progress['sources'][repo] = 'metadata_locked'
        v1.save(root / 'lock.json', {'image': image, 'sources': sources, 'metadataOnly': True,
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
        v1.save(root / 'result.json', progress)


def verify_saved(root, manifest, *, manifest_sha=MANIFEST_SHA):
    """Offline public JSON replay; synthetic signed-URI placeholders are not credentials."""
    root = Path(root)
    config, _ = manifest_info(Path(manifest).read_bytes(), manifest_sha)
    ledger = strict_json((root / 'http/ledger.json').read_bytes())
    require(sum(e['bodyBytes'] for e in ledger['events']) == ledger['receivedBodyBytes'] <= CAPS['totalBytes'], 'Saved byte sum/cap')
    require(len(ledger['events']) <= CAPS['attempts'], 'Saved attempt cap')
    synthetic = 'https://cdn01.quay.io' + cdn_path(config) + '?' + urlencode({k: 'redacted-placeholder' for k in QUERY_KEYS})
    for event in ledger['events']:
        require(0 <= event['bodyBytes'] <= CAPS['eachBytes'], 'Saved response cap')
        if event['kind'] == 'git':
            v1.endpoint(event['url'], 'git')
        else:
            uri = event['requestUri']
            require(uri['queryValuesRedacted'] and event['url'] == uri['scheme'] + '://' + uri['host'] + uri['path'], 'Saved URI redaction')
            target = public_uri(config_url(config) if event['kind'] == 'config' else synthetic, event['kind'], config)
            require(all(uri[k] == target[k] for k in ('scheme', 'host', 'path', 'queryParameterNames')), 'Saved config endpoint drift')
            require(0 < uri['urlBytes'] <= 4096, 'Saved URI size')
            v1.hash_id(uri['urlSha256'])
            require('location' not in event.get('headers', {}), 'Saved Location leakage')
        if event['bodyFile'] is not None:
            path = root / 'http' / event['bodyFile']
            require(path.parent == root / 'http' and re.fullmatch(r'[0-9]{3}\.bin', path.name), 'Saved spool path')
            body = path.read_bytes()
            require(len(body) == event['bodyBytes'] and hashlib.sha256(body).hexdigest() == event['bodySha256'], 'Saved metadata identity')
        else:
            require(event['kind'] in ('config', 'cdn') and event['privateBodyRedacted'], 'Saved redacted body')
            v1.hash_id(event['bodySha256'])
    state = strict_json((root / 'result.json').read_bytes())
    require(state['requests'] == len(ledger['events']) and state['receivedBodyBytes'] == ledger['receivedBodyBytes'], 'Saved result accounting')
    if state['status'] != 'metadata_locked_not_acquired':
        return {'ledgerVerified': True, 'completeLockReplayed': False, 'scope': 'Preserved stop; private body receipts only, no fabricated missing responses.'}
    class Replay:
        def __init__(self): self.index = 0
        def open(self, url, kind, headers, seconds):
            event = ledger['events'][self.index]
            self.index += 1
            expected = synthetic if kind == 'cdn' else event['url']
            require((url, kind) == (expected, event['kind']), 'Saved metadata state-machine drift')
            response_headers = dict(event.get('headers', {}))
            if event['kind'] == 'config' and event['status'] == 302:
                require(event['redirectReceipt']['host'] == 'cdn01.quay.io' and event['redirectReceipt']['path'] == cdn_path(config)
                    and event['redirectReceipt']['queryParameterNames'] == QUERY_KEYS, 'Saved redirect policy drift')
                body = b''
                response_headers.pop('transfer-encoding', None)
                response_headers['content-length'] = '0'
                response_headers['location'] = synthetic
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
        require(resolve(Path(temp), manifest, manifest_sha=manifest_sha, transport=replay) == 0
            and replay.index == len(ledger['events']), 'Offline lock replay')
        require((Path(temp) / 'lock.json').read_bytes() == (root / 'lock.json').read_bytes(), 'Offline lock differs')
    return {'ledgerVerified': True, 'completeLockReplayed': True,
        'scope': 'Public saved JSON replay; synthetic signed-URL/body placeholders prove policy and identities, not original URL values, signature authentication or redacted body contents. No network.'}
