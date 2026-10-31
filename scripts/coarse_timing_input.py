"""One metered, isolated road-attribute pilot. Never imported by the app."""
import argparse
from collections import OrderedDict
import hashlib
import http.client
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET


class PilotError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise PilotError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def canonical_etag(value):
    require(isinstance(value, str) and value and not value.startswith('W/'), 'Missing/weak object identity')
    if value.startswith('"'):
        require(value.endswith('"'), 'Malformed ETag')
        value = value[1:-1]
    require(value and all(33 <= ord(c) <= 126 and c not in '"\\' for c in value), 'Malformed ETag')
    return '"' + value + '"'


class Budget:
    def __init__(self, caps, root, clock=time.monotonic):
        self.caps, self.root, self.clock = caps, Path(root), clock
        self.started = clock()
        self.bytes = self.requests = self.tool_bytes = self.rows = 0
        self.stopped = False
        self.working_bytes = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
        self.append_sizes = {}

    def check(self):
        require(not self.stopped, 'Budget already stopped')
        require(self.clock() - self.started < self.caps['wallSeconds'], 'Wall-time cap')

    def stop(self, message):
        self.stopped = True
        raise PilotError(message)

    def request(self):
        self.check()
        if self.requests >= self.caps['httpRequests']:
            self.stop('HTTP request cap')
        self.requests += 1

    def receive(self, size, tool=False):
        self.check()
        if size < 0 or self.bytes + size > self.caps['receivedHttpBodyBytes']:
            self.stop('HTTP body-byte cap')
        if tool and self.tool_bytes + size > self.caps['toolDownloadBodyBytesWithinTotal']:
            self.stop('Tool-download cap')
        self.bytes += size
        if tool:
            self.tool_bytes += size

    def remaining(self, tool=False):
        remaining = self.caps['receivedHttpBodyBytes'] - self.bytes
        return min(remaining, self.caps['toolDownloadBodyBytesWithinTotal'] - self.tool_bytes) if tool else remaining

    def write(self, name, raw, replace=False):
        self.check()
        path = (self.root / name).resolve()
        require(path.is_relative_to(self.root.resolve()), 'Output escaped working directory')
        require(replace or not path.exists(), 'Output refuses overwrite: ' + name)
        old = path.stat().st_size if path.exists() else 0
        # Replacement temporarily retains both copies. Reserve checkpoint/tmp space.
        require(self.working_bytes + len(raw) + 128 * 1024 ** 2 <= self.caps['totalLocalWorkingBytes'], 'Working-storage cap')
        path.parent.mkdir(parents=True, exist_ok=True)
        if replace:
            temporary = path.with_name(path.name + '.partial')
            temporary.write_bytes(raw)
            temporary.replace(path)
        else:
            with path.open('xb') as stream:
                stream.write(raw)
        self.working_bytes += len(raw) - old
        return old

    def snapshot(self):
        return {'receivedHttpBodyBytes': self.bytes, 'toolBodyBytes': self.tool_bytes,
                'httpRequests': self.requests, 'uniqueRows': self.rows,
                'elapsedSeconds': self.clock() - self.started, 'stopped': self.stopped}

    def append(self, name, raw, limit):
        self.check()
        path = (self.root / name).resolve()
        require(path.is_relative_to(self.root.resolve()), 'Append escaped working directory')
        if name not in self.append_sizes:
            require(not path.exists(), 'Append output refuses overwrite')
            self.append_sizes[name] = 0
        require(self.append_sizes[name] + len(raw) <= limit, 'Retained-extract cap')
        require(self.working_bytes + len(raw) + 128 * 1024 ** 2 <= self.caps['totalLocalWorkingBytes'], 'Working-storage cap')
        with path.open('ab') as stream:
            stream.write(raw)
        self.append_sizes[name] += len(raw)
        self.working_bytes += len(raw)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class Meter:
    def __init__(self, budget, allowed_hosts, opener=None, record=None, save_body=None):
        self.budget, self.hosts = budget, set(allowed_hosts)
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.record = record or (lambda event: None)
        self.save_body = save_body or (lambda raw, event: None)

    def get(self, url, *, limit, headers=None, expected_status=200, etag=None, content_range=None, tool=False):
        parsed = urllib.parse.urlsplit(url)
        require(parsed.scheme == 'https' and parsed.hostname in self.hosts and
                not parsed.username and not parsed.password and parsed.port in (None, 443), 'Unlisted/nonpublic HTTPS URL')
        self.budget.request()
        event = {'requestNumber': self.budget.requests, 'url': url, 'receivedBodyBytes': 0, 'status': None, 'outcome': 'started'}
        self.record(event)
        response, body = None, bytearray()
        try:
            request = urllib.request.Request(url, headers={'Accept-Encoding': 'identity', 'User-Agent': 'geo-planner-timing-pilot/1', **(headers or {})})
            try:
                response = self.opener.open(request, timeout=min(30, max(.1, self.budget.caps['wallSeconds'] - (self.budget.clock() - self.budget.started))))
            except urllib.error.HTTPError as error:
                response = error
            event['status'] = response.status
            require(response.headers.get('Content-Encoding', 'identity') in ('identity', ''), 'Unexpected HTTP content encoding')
            length = response.headers.get('Content-Length')
            expected_length = int(length) if length is not None else None
            require(expected_length is None or expected_length >= 0, 'Invalid HTTP length')
            require(expected_length is None or expected_length <= limit, 'Response exceeds per-read bound')
            require(expected_length is None or expected_length <= self.budget.remaining(tool), 'HTTP body-byte cap before body')
            # Error/redirect bodies are bounded and metered too. Never follow redirects.
            valid = response.status == expected_status
            if etag is not None:
                valid = valid and canonical_etag(response.headers.get('ETag')) == canonical_etag(etag)
            if content_range is not None:
                valid = valid and response.headers.get('Content-Range') == content_range
            read_limit = limit if valid else min(limit, 64 * 1024)
            while True:
                self.budget.check()
                remaining = min(read_limit - len(body), self.budget.remaining(tool))
                if remaining == 0:
                    if expected_length == len(body):
                        break
                    raise PilotError('Response reached byte bound before verified EOF')
                try:
                    chunk = response.read(min(65536, remaining))
                except http.client.IncompleteRead as error:
                    self.budget.receive(len(error.partial), tool)
                    event['receivedBodyBytes'] += len(error.partial)
                    body.extend(error.partial)
                    raise PilotError('Truncated HTTP response') from error
                if not chunk:
                    break
                self.budget.receive(len(chunk), tool)
                event['receivedBodyBytes'] += len(chunk)
                body.extend(chunk)
                self.record(event)
            require(valid, f'HTTP status/range/identity mismatch ({response.status})')
            require(expected_length is None or len(body) == expected_length, 'Truncated HTTP response')
            event.update(outcome='complete', sha256=hashlib.sha256(body).hexdigest())
            return bytes(body), dict(response.headers)
        except Exception as error:
            self.budget.stopped = True
            event.update(outcome='failed', error=str(error)[:500])
            raise
        finally:
            if response is not None:
                response.close()
            event['bodySha256'] = hashlib.sha256(body).hexdigest()
            if response is not None and response.status >= 300:
                event['errorBodyUtf8'] = body.decode('utf-8', errors='replace')[:4096]
            self.save_body(bytes(body), event)
            self.record(event)


class RangeFile(io.RawIOBase):
    def __init__(self, meter, record):
        super().__init__()
        self.meter, self.record, self.position = meter, record, 0
        self.cache = OrderedDict()
        self.cached_bytes = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.record['bytes'] + offset if whence == 2 else -1
        require(0 <= position <= self.record['bytes'], 'Invalid Parquet seek')
        self.position = position
        return position

    def read(self, size=-1):
        size = self.record['bytes'] - self.position if size < 0 else min(size, self.record['bytes'] - self.position)
        require(size <= 64 * 1024 ** 2, 'Parquet read allocation cap')
        if not size:
            return b''
        key = (self.position, size)
        if key in self.cache:
            raw = self.cache.pop(key)
            self.cache[key] = raw
        else:
            end = self.position + size - 1
            raw, _ = self.meter.get(self.record['url'], limit=size,
                headers={'Range': f'bytes={self.position}-{end}', 'If-Match': self.record['etag']},
                expected_status=206, etag=self.record['etag'],
                content_range=f'bytes {self.position}-{end}/{self.record["bytes"]}')
            require(len(raw) == size, 'Truncated ranged read')
            while self.cache and self.cached_bytes + size > 64 * 1024 ** 2:
                _, removed = self.cache.popitem(last=False)
                self.cached_bytes -= len(removed)
            self.cache[key] = raw
            self.cached_bytes += size
        self.position += size
        return raw

    def readinto(self, buffer):
        raw = self.read(len(buffer))
        buffer[:len(raw)] = raw
        return len(raw)

    def close(self):
        self.cache.clear()
        self.cached_bytes = 0
        super().close()


def usable_limit(row):
    result = {'status': 'missing', 'kmh': None}
    if row.get('subtype') != 'road' or row.get('class') not in {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'residential', 'living_street', 'unclassified', 'service'}:
        return {**result, 'status': 'unsupported_road_role'}
    if row.get('access_restrictions'):
        return {**result, 'status': 'access_scoped_or_restricted'}
    rules = row.get('speed_limits')
    if rules is None or rules == []:
        return result
    if not isinstance(rules, list):
        return {**result, 'status': 'malformed'}
    values = {'forward': set(), 'backward': set()}
    for rule in rules:
        if not isinstance(rule, dict):
            return {**result, 'status': 'malformed'}
        if rule.get('between') not in (None, [0, 1], [0., 1.]):
            return {**result, 'status': 'partial_scope'}
        if rule.get('is_max_speed_variable'):
            return {**result, 'status': 'variable'}
        when = rule.get('when') or {}
        if not isinstance(when, dict):
            return {**result, 'status': 'malformed'}
        if any(value not in (None, [], {}) for key, value in when.items() if key != 'heading'):
            return {**result, 'status': 'conditional'}
        heading = when.get('heading')
        if heading not in (None, 'forward', 'backward'):
            return {**result, 'status': 'unsupported_heading'}
        speed = rule.get('max_speed')
        if speed is None:
            return {**result, 'status': 'no_explicit_maximum'}
        if not isinstance(speed, dict) or isinstance(speed.get('value'), bool) or not isinstance(speed.get('value'), (int, float)):
            return {**result, 'status': 'malformed'}
        value, unit = speed['value'], speed.get('unit')
        if not math.isfinite(value) or value <= 0:
            return {**result, 'status': 'malformed'}
        if unit not in ('mph', 'km/h'):
            return {**result, 'status': 'unsupported_unit'}
        kmh = value * (1.609344 if unit == 'mph' else 1)
        for direction in ((heading,) if heading else ('forward', 'backward')):
            values[direction].add(kmh)
    if any(len(v) > 1 for v in values.values()):
        return {**result, 'status': 'conflicting'}
    if not values['forward'] or values['forward'] != values['backward']:
        return {**result, 'status': 'directional'}
    return {'status': 'usable', 'kmh': next(iter(values['forward']))}


def list_objects(meter, source):
    root = urllib.parse.urlsplit(source['dataRoot'])
    container, prefix = root.path.lstrip('/').split('/', 1)
    require(root.hostname == 'overturemapswestus2.blob.core.windows.net' and container == 'release', 'Unexpected publisher root')
    result, marker, seen = [], '', {''}
    while True:
        query = urllib.parse.urlencode({'restype': 'container', 'comp': 'list', 'prefix': prefix, 'maxresults': 5000, 'marker': marker})
        raw, _ = meter.get(f'https://{root.hostname}/{container}?{query}', limit=16 * 1024 ** 2)
        tree = ET.fromstring(raw)
        for blob in tree.findall('./Blobs/Blob'):
            name = blob.findtext('Name')
            require(name and name.startswith(prefix), 'Publisher prefix changed')
            if not name.endswith('.parquet'):
                continue
            size = int(blob.findtext('./Properties/Content-Length'))
            etag = blob.findtext('./Properties/Etag') or blob.findtext('./Properties/ETag')
            require(size > 12, 'Invalid object size')
            result.append({'url': f'https://{root.hostname}/{container}/' + urllib.parse.quote(name, safe='/='), 'bytes': size, 'etag': canonical_etag(etag)})
        next_marker = tree.findtext('NextMarker') or ''
        require(not next_marker or next_marker not in seen, 'Repeated listing continuation')
        if not next_marker:
            break
        marker = next_marker
        seen.add(marker)
    require(result, 'Pinned release has no segment objects; no fallback')
    require(len({r['url'] for r in result}) == len(result), 'Duplicate publisher object')
    return sorted(result, key=lambda r: r['url'])


def cgroup_limit():
    path = Path('/sys/fs/cgroup')
    require(sys.platform == 'linux', 'Hard memory guard requires isolated Linux cgroup')
    memory = int((path / 'memory.max').read_text().strip())
    swap = int((path / 'memory.swap.max').read_text().strip())
    require(0 < memory <= 1024 ** 3 and swap == 0, 'Memory/swap cap not enforced')
    return {'memoryMaxBytes': memory, 'swapMaxBytes': swap}


def start_watchdog(seconds):
    require(os.getpid() != 1, 'Worker requires an init supervisor for hard timeout')
    program = 'import os,signal,sys,time; time.sleep(float(sys.argv[1])); os.kill(int(sys.argv[2]),signal.SIGKILL)'
    return subprocess.Popen([sys.executable, '-B', '-c', program, str(seconds), str(os.getpid())],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def worker(plan_path, output, expected_sha):
    require(digest(plan_path) == expected_sha, 'Worker execution-plan binding')
    plan = json.loads(Path(plan_path).read_text())
    proposal = json.loads(Path('/inputs/proposal.json').read_text())
    require(digest('/inputs/proposal.json') == plan['proposalSha256'], 'Proposal binding')
    for name, sha in plan['codeFiles'].items():
        require(digest(Path('/code') / name) == sha, name)
    root = Path(output)
    require(not (root / 'state.json').exists(), 'Capture refuses overwrite')
    budget = Budget(proposal['hardCaps'], root)
    state = {'status': 'preflight', 'stage': 'memory_guard', 'windows': [
        {'id': w['id'], 'status': 'unmeasured'} for w in proposal['selection']['windows']], 'network': [], 'routingQueries': 0}
    def checkpoint(event=None):
        if event is not None:
            if state['network'] and state['network'][-1].get('url') == event['url'] and state['network'][-1].get('outcome') == 'started':
                state['network'][-1] = dict(event)
            else:
                state['network'].append(dict(event))
        state['budget'] = budget.snapshot()
        # Failure records must remain writable after the work budget stops.
        raw = json_bytes(state)
        require(len(raw) <= 16 * 1024 ** 2, 'Ledger cap')
        temporary = root / 'state.json.partial'
        temporary.write_bytes(raw)
        temporary.replace(root / 'state.json')
    def save_body(raw, event):
        # Preserve failed responses too, without exceeding storage or replacing
        # the original error when a work/time budget has already stopped.
        if budget.working_bytes + len(raw) + 128 * 1024 ** 2 > budget.caps['totalLocalWorkingBytes']:
            event['bodyFileOmitted'] = 'working-storage cap; checksum retained'
            return
        name = f'http/{event["requestNumber"]:05d}.bin'
        path = root / name
        path.parent.mkdir(exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
        budget.working_bytes += len(raw)
        event['bodyFile'] = name
    watchdog = None
    try:
        state['memoryGuard'] = cgroup_limit()
        require(state['memoryGuard']['memoryMaxBytes'] == proposal['hardCaps']['processRssBytes'], 'Frozen memory cap differs')
        watchdog = start_watchdog(proposal['hardCaps']['wallSeconds'])
        checkpoint()
        meter = Meter(budget, plan['allowedHosts'], record=checkpoint, save_body=save_body)
        state.update(stage='publisher_manifest', status='running')
        checkpoint()
        objects = list_objects(meter, proposal['source'])
        budget.write('object-manifest.json', json_bytes({'source': proposal['source'], 'objects': objects}))
        state['stage'] = 'parquet_tool_and_readiness'
        checkpoint()
        from coarse_timing_parquet import capture
        report = capture(plan, proposal, objects, budget, meter, state, checkpoint)
        state.update(status='data_complete_review_pending' if report['coverageScreenPassed'] else 'data_complete_feasibility_failed', stage='complete', report=report)
    except Exception as error:
        budget.stopped = True
        state.update(status='stopped', error=str(error)[:2000], errorType=type(error).__name__)
        for window in state['windows']:
            if window['status'] == 'unmeasured':
                window['status'] = 'unmeasured_after_stop'
        checkpoint()
        return 2
    finally:
        if watchdog and watchdog.poll() is None:
            watchdog.terminate()
            watchdog.wait(timeout=5)
    checkpoint()
    return 0


def driver(output, expected_sha):
    repo = Path(__file__).resolve().parents[1]
    plan_path = repo / 'docs/evidence/coarse-timing-pilot-2026-10-25/execution-plan.json'
    require(digest(plan_path) == expected_sha, 'Execution-plan binding')
    plan = json.loads(plan_path.read_text())
    for name, sha in plan['inputs'].items():
        require(digest(repo / name) == sha, name)
    root = (repo / output).resolve()
    require(root == (repo / plan['output']).resolve() and root.is_relative_to(repo / 'data/coarse-quality'), 'Output path differs')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(plan_path.read_bytes())
    name = 'geo-planner-timing-' + uuid.uuid4().hex[:12]
    (root / 'container-name.txt').write_text(name + '\n')
    command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--label', 'geo-planner.timing-plan=' + expected_sha,
               '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=1g', '--memory-swap=1g',
               '--cpus=2', '--pids-limit=64', '--tmpfs=/tmp:rw,size=64m',
               '--mount', f'type=bind,src={repo / "scripts"},dst=/code,readonly',
               '--mount', f'type=bind,src={root},dst=/work',
               '--mount', f'type=bind,src={plan_path},dst=/inputs/plan.json,readonly',
               '--mount', f'type=bind,src={repo / plan["proposal"]},dst=/inputs/proposal.json,readonly',
               '--mount', f'type=bind,src={repo / plan["geometryReport"]},dst=/inputs/geometry-report.json,readonly',
               '--mount', f'type=bind,src={repo / plan["geometryDirectory"]},dst=/geometry,readonly',
               '--entrypoint=python3', plan['containerImageId'], '-B', '/code/coarse_timing_input.py', '--worker', '/inputs/plan.json', '/work', '--expected-plan-sha', expected_sha]
    identity = None
    try:
        started = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        identity = result.stdout.strip()
        require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Invalid owned container identity')
        with (root / 'worker.log').open('xb') as log:
            result = subprocess.run(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT, timeout=max(1, plan['wallSeconds'] - (time.monotonic() - started)))
        inspect = subprocess.run(['docker', 'inspect', identity], capture_output=True, text=True, check=True, timeout=30)
        inspected = json.loads(inspect.stdout)[0]
        summary = {'State': inspected['State'], 'Image': inspected['Image'],
                   'Limits': {k: inspected['HostConfig'][k] for k in ['Memory', 'MemorySwap', 'ReadonlyRootfs', 'NetworkMode']}}
        (root / 'container-result.json').write_bytes(json_bytes(summary))
        if result.returncode and (root / 'state.json').exists():
            last = json.loads((root / 'state.json').read_text())
            (root / 'driver-stop.json').write_bytes(json_bytes({'workerExitCode': result.returncode, 'lastCheckpoint': last,
                'complete': False, 'reason': 'Owned worker stopped; never resume or replace this run'}))
        print(json.dumps({'workerExitCode': result.returncode, 'state': str(root / 'state.json')}, indent=2))
        return result.returncode
    except Exception as error:
        proposal = json.loads((repo / plan['proposal']).read_text())
        (root / 'driver-failure.json').write_bytes(json_bytes({'error': str(error)[:1000], 'ownedContainer': identity, 'pilotComplete': False,
            'windows': [{'id': w['id'], 'status': 'unmeasured_or_incomplete_after_driver_stop'} for w in proposal['selection']['windows']]}))
        raise
    finally:
        if identity:
            subprocess.run(['docker', 'rm', '-f', identity], capture_output=True, check=False, timeout=30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--expected-plan-sha')
    parser.add_argument('output')
    parser.add_argument('plan_sha256')
    args = parser.parse_args()
    raise SystemExit(worker(args.output, args.plan_sha256, args.expected_plan_sha) if args.worker else driver(args.output, args.plan_sha256))
