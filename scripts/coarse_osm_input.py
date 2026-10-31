"""Metered native-OSM capture controls. No parser, matcher or app integration."""
from collections import Counter
from contextlib import contextmanager
import hashlib
import http.client
import json
import math
from pathlib import Path
import re
import signal
import time
from urllib.parse import urlencode, urlsplit

from coarse_osm_records import batch, canonical, utc
from coarse_timing_input import PilotError, digest, json_bytes, require


PLAN = 'docs/evidence/coarse-osm-pilot-2026-10-26/execution-plan.json'
STATE_RESERVE = 8 * 1024 ** 2


@contextmanager
def absolute_timeout(seconds):
    require(seconds > 0 and signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'Absolute deadline unavailable/already active')
    def expired(*_): raise PilotError('HTTP absolute deadline')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try: yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.)
        signal.signal(signal.SIGALRM, previous)


class Budget:
    def __init__(self, caps, root, clock=time.monotonic):
        self.caps, self.root, self.clock = caps, Path(root).resolve(), clock
        self.started = clock()
        self.received = self.attempts = self.unique = self.occurrences = self.extract = 0
        self.disk = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
        self.initial_disk = self.disk
        self.stopped = False

    def check(self):
        require(not self.stopped, 'Capture already stopped')
        require(self.clock() - self.started < self.caps['wallSeconds'], 'Global wall-time cap')

    def path(self, name):
        path = (self.root / name).resolve()
        require(path.is_relative_to(self.root) and path != self.root, 'Unsafe capture output path')
        return path

    def room(self):
        return self.caps['workingBytes'] - self.disk - self.caps['tmpBytes'] - STATE_RESERVE

    def append(self, name, raw, *, preserve=False, extract=False):
        if not preserve: self.check()
        require(len(raw) <= self.room(), 'Working-storage cap')
        if extract: require(self.extract + len(raw) <= self.caps['normalizedExtractBytes'], 'Normalized-extract cap')
        path = self.path(name); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('ab', buffering=0) as stream:
            require(stream.write(raw) == len(raw), 'Incomplete capture write')
        self.disk += len(raw)
        if extract: self.extract += len(raw)

    def create(self, name):
        path = self.path(name); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb'): pass

    def snapshot(self):
        return {'receivedHttpBodyBytes': self.received, 'httpAttempts': self.attempts, 'uniqueNormalizedElements': self.unique,
            'validatedElementOccurrences': self.occurrences, 'normalizedExtractBytes': self.extract,
            'elapsedSeconds': self.clock() - self.started, 'accountedWorkingBytes': self.disk,
            'initialWorkingBytes': self.initial_disk,
            'reservedTmpBytes': self.caps['tmpBytes'], 'reservedStateDriverBytes': STATE_RESERVE, 'stopped': self.stopped}


class NativeResponse:
    def __init__(self, connection, response):
        self.connection, self.response, self.status = connection, response, response.status
        self.headers = response.getheaders()

    def read1(self, size): return self.response.read1(size)

    def close(self):
        try: self.response.close()
        finally: self.connection.close()


class DirectHttps:
    """http.client does not inherit proxy/cookie/auth handlers or follow redirects."""
    def open(self, method, url, body, timeout):
        parsed = urlsplit(url)
        require(parsed.scheme == 'https' and parsed.hostname == 'overpass-api.de' and parsed.port in (None, 443)
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment, 'Unlisted HTTPS endpoint')
        require((method, parsed.path) in (('GET', '/api/status'), ('POST', '/api/interpreter')), 'Unlisted method/path')
        headers = {'User-Agent': 'geo-planner-osm-pilot/1 (finite offline research)', 'Accept-Encoding': 'identity', 'Connection': 'close'}
        if method == 'POST': headers['Content-Type'] = 'application/x-www-form-urlencoded'
        connection = http.client.HTTPSConnection('overpass-api.de', 443, timeout=timeout)
        try:
            connection.request(method, parsed.path, body=body, headers=headers)
            return NativeResponse(connection, connection.getresponse())
        except BaseException:
            connection.close(); raise


class Meter:
    def __init__(self, proposal, queries, budget, events, checkpoint, transport=None, alarm=absolute_timeout):
        self.proposal, self.queries, self.budget = proposal, queries, budget
        self.events, self.checkpoint = events, checkpoint
        self.transport, self.alarm = transport or DirectHttps(), alarm
        self.sequence = [(kind, q['id']) for q in queries for kind in ('status', 'query')]

    def fetch(self, kind, query):
        budget = self.budget; budget.check()
        require(budget.attempts < self.proposal['hardCaps']['httpAttempts'], 'HTTP attempt cap')
        require(budget.received < budget.caps['totalHttpBodyBytes'] and budget.room() > 0, 'HTTP body/working-storage cap before request')
        require(budget.attempts < len(self.sequence) and self.sequence[budget.attempts] == (kind, query['id']), 'HTTP request order/retry violation')
        source = self.proposal['source']; method = 'GET' if kind == 'status' else 'POST'
        url = source['statusUrl' if kind == 'status' else 'queryUrl']
        require(url == 'https://overpass-api.de/api/' + ('status' if kind == 'status' else 'interpreter'), 'Source endpoint changed')
        body = None if kind == 'status' else urlencode({'data': query['text']}).encode()
        if body is not None:
            require(hashlib.sha256(body).hexdigest() == query['formBodySha256'] and len(body) == query['formBodyBytes'], 'Frozen request body changed')
        limit = budget.caps['statusAcceptedBodyBytes' if kind == 'status' else 'queryAcceptedBodyBytes']
        seconds = self.proposal['timeouts']['statusAbsoluteClientSeconds' if kind == 'status' else 'queryAbsoluteClientSeconds']
        seconds = min(seconds, budget.caps['wallSeconds'] - (budget.clock() - budget.started))
        budget.attempts += 1
        event = {'number': budget.attempts, 'windowId': query['id'], 'kind': kind, 'method': method, 'url': url,
            'formBodySha256': None if body is None else hashlib.sha256(body).hexdigest(), 'status': None,
            'receivedBodyBytes': 0, 'bodyFile': f'http/{budget.attempts:05d}.bin', 'outcome': 'started',
            'startedElapsedSeconds': budget.clock() - budget.started, 'absoluteTimeoutSeconds': seconds,
            'bodyCounterScope': 'Payload bytes returned by read1/IncompleteRead.partial; excludes headers/TCP/TLS/kernel buffering.'}
        budget.create(event['bodyFile']); self.events.append(event); self.checkpoint()
        hasher, response, began = hashlib.sha256(), None, budget.clock()
        def save(chunk):
            require(isinstance(chunk, bytes), 'Nonbinary HTTP body')
            budget.received += len(chunk); event['receivedBodyBytes'] += len(chunk); hasher.update(chunk)
            budget.append(event['bodyFile'], chunk, preserve=True)
            self.checkpoint()
        try:
            with self.alarm(seconds):
                response = self.transport.open(method, url, body, seconds)
                event['status'] = response.status
                headers = {}
                for name, value in response.headers:
                    key = name.lower()
                    require(isinstance(value, str) and len(value) <= 4096, 'Invalid/oversized response header')
                    if key in ('content-length', 'content-encoding', 'transfer-encoding', 'content-type', 'location'):
                        require(key not in headers, 'Duplicate framing/content header'); headers[key] = value
                event['headers'] = headers
                require(headers.get('content-encoding', 'identity').strip().lower() in ('identity', ''), 'Unexpected compressed encoding')
                require(not ('content-length' in headers and 'transfer-encoding' in headers), 'Conflicting HTTP framing')
                require(headers.get('transfer-encoding', 'chunked').strip().lower() == 'chunked', 'Unsupported transfer encoding')
                length = headers.get('content-length')
                require(length is None or re.fullmatch(r'\d{1,20}', length), 'Invalid Content-Length')
                expected = None if length is None else int(length)
                require(expected is None or expected <= limit, 'Declared HTTP body exceeds response cap')
                require(expected is None or expected <= budget.caps['totalHttpBodyBytes'] - budget.received, 'Declared HTTP body exceeds total cap')
                while expected is None or event['receivedBodyBytes'] < expected:
                    budget.check(); require(budget.clock() - began < seconds, 'HTTP absolute deadline')
                    size = min(65536, limit + 1 - event['receivedBodyBytes'], budget.caps['totalHttpBodyBytes'] - budget.received, budget.room())
                    require(size > 0, 'HTTP body/working-storage cap')
                    try: chunk = response.read1(size)
                    except http.client.IncompleteRead as error:
                        require(len(error.partial) <= size, 'HTTP partial exceeded requested read bound')
                        save(error.partial); raise PilotError('Truncated HTTP body') from error
                    require(len(chunk) <= size, 'HTTP transport exceeded requested read bound')
                    if not chunk: break
                    save(chunk)
                    require(event['receivedBodyBytes'] <= limit, 'Streamed HTTP body exceeds response cap')
                    require(budget.clock() - began < seconds, 'HTTP absolute deadline')
                require(expected is None or event['receivedBodyBytes'] == expected, 'Truncated HTTP body')
                require(budget.clock() - began < seconds, 'HTTP absolute deadline')
                require(response.status == 200, f'HTTP refusal/status {response.status}')
                if kind == 'query': require(headers.get('content-type', '').split(';')[0].strip().lower() == 'application/json', 'Unexpected query Content-Type')
                response.close(); response = None
                require(budget.clock() - began < seconds, 'HTTP absolute deadline')
                event['outcome'] = 'complete'
            return budget.path(event['bodyFile'])
        except Exception as error:
            event.update(outcome='failed', errorType=type(error).__name__, error=str(error)[:1000])
            raise
        finally:
            try:
                if response is not None: response.close()
            finally:
                event.update(bodySha256=hasher.hexdigest(), finishedElapsedSeconds=budget.clock() - budget.started)
                self.checkpoint()


def status_wait(raw, snapshot, maximum):
    text = raw.decode('utf-8')
    current = re.findall(r'^Current time: (\S+)\s*$', text, re.M)
    rates = re.findall(r'^Rate limit: (\d+)\s*$', text, re.M)
    require(len(current) == len(rates) == 1 and int(rates[0]) > 0, 'Malformed Overpass status')
    now = utc(current[0]); require(now >= utc(snapshot), 'Stale status timestamp')
    available = re.findall(r'^(\d+) slots? available now\.\s*$', text, re.M)
    require(len(available) <= 1, 'Duplicate status availability')
    if available and int(available[0]) > 0:
        require(int(available[0]) <= int(rates[0]), 'Invalid status slot count')
        return 0.
    slots = re.findall(r'^Slot available after: (\S+), in (\d+) seconds?\.\s*$', text, re.M)
    require(slots, 'Status has no available slot/time')
    waits = []
    for at, reported in slots:
        wait = (utc(at) - now).total_seconds()
        require(wait >= 0 and abs(wait - int(reported)) <= 1, 'Malformed status wait')
        waits.append(wait)
    result = min(waits)
    require(result <= maximum, 'Status wait exceeds bound')
    return result


def capture(proposal, queries, root, *, transport=None, clock=time.monotonic, sleep=time.sleep, alarm=absolute_timeout):
    budget = Budget(proposal['hardCaps'], root, clock)
    require(not budget.path('state.json').exists() and not budget.path('elements.jsonl').exists(), 'Capture refuses overwrite')
    budget.create('elements.jsonl')
    state = {'status': 'running', 'stage': 'preflight', 'windows': [{'id': q['id'], 'status': 'unmeasured'} for q in queries],
        'http': [], 'snapshotUtc': proposal['source']['snapshotUtc'], 'sourceGenerator': None,
        'routingProviderRequests': 0, 'sourceAdapterImplemented': False, 'originalFeasibilityQualified': False}
    def checkpoint():
        state['budget'] = budget.snapshot()
        raw = json_bytes(state); require(len(raw) <= STATE_RESERVE // 4, 'Capture ledger cap')
        temporary = budget.path('state.json.partial'); temporary.write_bytes(raw); temporary.replace(budget.path('state.json'))
    meter = Meter(proposal, queries, budget, state['http'], checkpoint, transport, alarm)
    known = {}; totals = Counter()
    checkpoint()
    try:
        for query, window in zip(queries, state['windows'], strict=True):
            budget.check(); state['stage'] = 'status'; window['status'] = 'status_requested'; checkpoint()
            status_path = meter.fetch('status', query)
            wait = status_wait(status_path.read_bytes(), state['snapshotUtc'], proposal['timeouts']['maximumStatusDirectedWaitSeconds'])
            window['statusWaitSeconds'] = wait
            if wait:
                require(wait < budget.caps['wallSeconds'] - (budget.clock() - budget.started), 'Global deadline before status wait')
                state['stage'] = 'status_wait'; checkpoint(); sleep(wait); budget.check()
            state['stage'] = 'query'; window['status'] = 'query_requested'; checkpoint()
            response_path = meter.fetch('query', query)
            state['stage'] = 'validate_response'; checkpoint()
            result = batch(response_path.read_bytes(), state['snapshotUtc'], query['bbox'], budget.caps, state['sourceGenerator'])
            count = len(result['records']); budget.occurrences += count
            require(budget.occurrences <= budget.caps['elementOccurrencesAllWindows'], 'Decoded element occurrence cap')
            incoming = []
            for record in result['records']:
                e = record['element']; key = e['type'], e['id']; identity = (e['version'], record['elementSha256'], record.get('geometryDependencySha256'))
                require(key not in known or known[key] == identity, 'Conflicting duplicate source/dependency identity')
                if key not in known: incoming.append((key, identity, record))
            require(len(known) + len(incoming) <= budget.caps['uniqueSourceElementsAllTypes'], 'Unique source element cap')
            state['sourceGenerator'] = result['generator']; window.update(status='normalizing', receivedElements=count,
                counts=result['counts'], sourceBaseTimestamp=result['sourceBaseTimestamp'], copyright=result['copyright'],
                newUniqueElements=0)
            checkpoint()
            for key, identity, record in incoming:
                encoded = canonical({'firstWindowId': query['id'], **record}) + b'\n'
                require(len(encoded) <= budget.caps['singleNormalizedElementBytes'], 'Single normalized element cap')
                budget.append('elements.jsonl', encoded, extract=True)
                known[key] = identity; budget.unique += 1; window['newUniqueElements'] += 1
                if budget.unique % 128 == 0: checkpoint()
            report = {k: v for k, v in result.items() if k != 'records'}
            report.update(id=query['id'], status='capture_complete', newUniqueElements=window['newUniqueElements'],
                sourceFeasibilityQualified=False, physicalIdentityVerified=False, carAccessVerified=False)
            encoded = json_bytes(report)
            require(len(encoded) <= budget.caps['singleNormalizedElementBytes'], 'Window inventory cap')
            name = 'windows/' + query['id'] + '.json'; budget.create(name); budget.append(name, encoded)
            totals.update(result['counts']); window.update(status='capture_complete', reportPath=name, reportSha256=hashlib.sha256(encoded).hexdigest()); checkpoint()
        budget.check()
        state.update(status='captured_all_windows_analysis_pending', stage='complete', totals=dict(totals))
        checkpoint(); return state
    except Exception as error:
        budget.stopped = True
        state.update(status='stopped', errorType=type(error).__name__, error=str(error)[:2000])
        for w in state['windows']:
            if w['status'] == 'unmeasured': w['status'] = 'unmeasured_after_stop'
            elif w['status'] != 'capture_complete': w['status'] = 'incomplete_after_stop'
        checkpoint(); return state


if __name__ == '__main__':
    from run_osm_capture import main
    main()
