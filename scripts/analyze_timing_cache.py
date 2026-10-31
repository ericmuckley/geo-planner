"""Offline partial-cache accounting; never fetch, route or qualify a model."""
import argparse
import base64
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import cgroup_limit, digest, json_bytes, require, start_watchdog, usable_limit
from coarse_timing_parquet import (MatchIndex, clip_segment, decode_lines, interpolate,
                                  intersects, load_source, source_spans)
from coarse_path_features import distance_km


EVIDENCE = 'docs/evidence/coarse-timing-cache-2026-10-25'
FIELDS = ['access_restrictions', 'connectors', 'level_rules', 'prohibited_transitions',
          'road_flags', 'sources', 'speed_limits', 'subclass', 'subclass_rules']


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class Output:
    def __init__(self, root, cap, seconds, clock=time.monotonic):
        self.root, self.cap, self.clock = Path(root), cap, clock
        self.started, self.bytes = clock(), 0
        self.seconds = seconds

    def check(self):
        require(self.clock() - self.started < self.seconds, 'Offline wall-time cap')

    def write(self, name, raw, append=False):
        self.check()
        path = self.root / name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe output path')
        require(self.bytes + len(raw) <= self.cap, 'Offline output cap')
        path.parent.mkdir(exist_ok=True, parents=True)
        with path.open('ab' if append else 'xb') as stream:
            stream.write(raw)
        self.bytes += len(raw)

    def record(self, name, value):
        self.write(name, canonical(value) + b'\n', append=True)


def observations(row):
    flags = {name + '_present' for name in FIELDS if row.get(name) not in (None, [], {})}
    rules = row.get('speed_limits')
    if rules in (None, []):
        flags.add('speed_limits_missing')
    elif not isinstance(rules, list):
        flags.add('malformed_speed_rule')
    else:
        for rule in rules:
            if not isinstance(rule, dict):
                flags.add('malformed_speed_rule')
                continue
            if rule.get('between') not in (None, [0, 1]):
                flags.add('partial_speed_rule')
            if rule.get('is_max_speed_variable'):
                flags.add('variable_speed_rule')
            when = rule.get('when') or {}
            if not isinstance(when, dict):
                flags.add('malformed_speed_rule')
            else:
                if when.get('heading') is not None:
                    flags.add('directional_speed_rule')
                if any(v not in (None, [], {}) for k, v in when.items() if k != 'heading'):
                    flags.add('conditional_speed_rule')
            speed = rule.get('max_speed')
            if speed is None:
                flags.add('no_explicit_maximum_rule')
            elif not isinstance(speed, dict):
                flags.add('malformed_speed_rule')
            elif speed.get('unit') not in ('mph', 'km/h'):
                flags.add('unsupported_speed_unit')
    return sorted(flags)


def clipped_km(lines, box):
    lengths = []
    for line in lines:
        for a, b in zip(line, line[1:]):
            clip = clip_segment(a, b, box)
            if clip:
                lengths.append(distance_km(interpolate(a, b, clip[0]), interpolate(a, b, clip[1])))
    return math.fsum(lengths)


def prepare_row(row, windows):
    require(isinstance(row.get('id'), str) and type(row.get('version')) is int, 'Invalid retained identity')
    require(row.get('subtype') == 'road' and isinstance(row.get('class'), str), 'Invalid retained road role')
    bbox = row['bbox']
    box = [bbox[k] for k in ['xmin', 'ymin', 'xmax', 'ymax']]
    require(all(math.isfinite(v) for v in box) and box[0] <= box[2] and box[1] <= box[3], 'Invalid retained bbox')
    members = [w for w in windows if intersects(box, w['bbox'])]
    require(members, 'Retained road outside every frozen window')
    try:
        lines = decode_lines(base64.b64decode(row['geometryWkbBase64'], validate=True))
        geometry_status = 'decoded'
    except (ValueError, RuntimeError):
        lines, geometry_status = [], 'malformed_geometry'
    limit = usable_limit(row)
    record = {
        'id': row['id'], 'version': row['version'], 'class': row['class'],
        'fieldsSha256': hashlib.sha256(canonical({k: v for k, v in row.items() if k != 'geometryWkbBase64'})).hexdigest(),
        'geometryBase64Sha256': hashlib.sha256(row['geometryWkbBase64'].encode()).hexdigest(),
        'geometryStatus': geometry_status, 'limit': limit,
        'speedOnlyLimit': usable_limit({**row, 'access_restrictions': None}),
        'observations': observations(row),
        'memberships': [{'windowId': w['id'], 'clippedGeometryKm': clipped_km(lines, w['bbox'])} for w in members],
    }
    slim = {k: row[k] for k in ['id', 'version', 'class']}
    slim.update(_lines=lines, _limit=limit)
    return record, slim


def empty_group():
    return {'bboxCandidateRows': 0, 'rowsWithClippedGeometry': 0, 'clippedGeometryKm': 0.,
            'limitStatusCounts': Counter(), 'limitStatusGeometryKm': defaultdict(float),
            'speedOnlyStatusCounts': Counter(), 'speedOnlyStatusGeometryKm': defaultdict(float),
            'observationCounts': Counter(), 'observationGeometryKm': defaultdict(float)}


def add_row(group, record, km):
    group['bboxCandidateRows'] += 1
    group['rowsWithClippedGeometry'] += km > 0
    group['clippedGeometryKm'] += km
    for prefix, key in [('limit', 'limit'), ('speedOnly', 'speedOnlyLimit')]:
        status = record[key]['status']
        group[prefix + 'StatusCounts'][status] += 1
        group[prefix + 'StatusGeometryKm'][status] += km
    group['observationCounts'].update(record['observations'])
    for flag in record['observations']:
        group['observationGeometryKm'][flag] += km


def cache_match(matcher, spans):
    result = matcher.match(spans)
    status = 'single_in_cache' if result['candidateCount'] == 1 else 'ambiguous_in_cache' if result['candidateCount'] > 1 else 'absent_in_cache'
    record = {k: v for k, v in result.items() if k not in ['status', 'usableKm']}
    record.update(status=status, provisionalStaticLimitMatchedKm=result['usableKm'], sourceComplete=False)
    if result['candidateCount'] == 1:
        record['limitStatus'] = result['limit']['status']
    return record


def analyze(plan, output, source_path, proposal, data):
    windows = proposal['selection']['windows']
    summaries = {w['id']: {'id': w['id'], 'sourceStatus': 'incomplete_after_capture_stop',
                 'publisherClasses': {}, 'publisherTotals': empty_group(), 'sourceClassesKph': {}} for w in windows}
    selected = defaultdict(list)
    seen, classes, field_counts, global_limits, global_flags = set(), set(), Counter(), Counter(), Counter()
    expected = set(proposal['columns']) - {'geometry'} | {'geometryWkbBase64'}
    with Path(source_path).open('rb') as stream:
        for raw in iter(lambda: stream.readline(plan['maxLineBytes'] + 1), b''):
            output.check()
            require(len(raw) <= plan['maxLineBytes'], 'Retained row allocation cap')
            row = json.loads(raw)
            require(set(row) == expected, 'Retained field/schema mismatch')
            key = row['id'], row['version']
            require(key not in seen and len(seen) < plan['expectedRows'], 'Duplicate or excess retained identity')
            seen.add(key)
            record, slim = prepare_row(row, windows)
            record['rawLineSha256'] = hashlib.sha256(raw).hexdigest()
            output.record('rows.jsonl', record)
            classes.add(row['class'])
            field_counts.update(k for k in expected if row[k] not in (None, [], {}))
            global_limits.update([record['limit']['status']])
            global_flags.update(record['observations'])
            for member in record['memberships']:
                wid, km = member['windowId'], member['clippedGeometryKm']
                selected[wid].append(slim)
                summary = summaries[wid]
                add_row(summary['publisherTotals'], record, km)
                group = summary['publisherClasses'].setdefault(row['class'], empty_group())
                add_row(group, record, km)
    require(len(seen) == plan['expectedRows'], 'Retained row count mismatch')
    for window in windows:
        output.check()
        wid, summary = window['id'], summaries[window['id']]
        for role in sorted(classes):
            summary['publisherClasses'].setdefault(role, empty_group())
        matcher = MatchIndex(selected[wid], window['bbox'])
        for speed in (85, 105):
            summary['sourceClassesKph'][str(speed)] = {'arcCount': 0, 'sourceKm': 0., 'cacheStatusCounts': Counter(),
                'cacheStatusSourceKm': defaultdict(float), 'singleCandidateLimitStatusSourceKm': defaultdict(float),
                'provisionalStaticLimitMatchedKm': 0.}
        for arc, spans in source_spans(data, plan['grid'], window['bbox']):
            output.check()
            speed = str(int(data['arcSpeedKph'][arc]))
            require(speed in summary['sourceClassesKph'], 'Unexpected Census source class')
            record = cache_match(matcher, spans)
            record.update(arc=arc, windowId=wid, sourceClassKph=int(speed), sourceSpans=spans)
            output.record('matches.jsonl', record)
            group = summary['sourceClassesKph'][speed]
            group['arcCount'] += 1
            group['sourceKm'] += record['sourceKm']
            group['cacheStatusCounts'][record['status']] += 1
            group['cacheStatusSourceKm'][record['status']] += record['sourceKm']
            group['provisionalStaticLimitMatchedKm'] += record['provisionalStaticLimitMatchedKm']
            if record['candidateCount'] == 1:
                group['singleCandidateLimitStatusSourceKm'][record['limitStatus']] += record['sourceKm']
        output.write('windows/' + wid + '.json', json_bytes(summary))
        print(json.dumps({'window': wid, 'cachedRows': len(selected[wid]), 'sourceStatus': summary['sourceStatus']}), flush=True)
    report = {'retainedUniqueRows': len(seen), 'fieldNonemptyCounts': field_counts,
              'limitStatusCounts': global_limits, 'observationCounts': global_flags,
              'windows': list(summaries.values()), 'completedSourceWindows': 0, 'plannedWindows': len(windows),
              'originalFeasibilityQualified': False, 'routingQueries': 0, 'networkRequests': 0,
              'naturalEarthBase': {'includedInCensusDenominator': False, 'status': 'unresolved_alignment'},
              'scope': 'Cached observations only. Source km use original Census cumulative weights per window membership. Publisher geometry km are clipped geodesic approximations, not Census weights. Single-in-cache candidates are provisional, not globally unique or a lower bound on final usable coverage. Speed limits are not journey speeds.'}
    output.write('report.json', json_bytes(report))


def worker(plan_path, root, expected_sha):
    require(digest(plan_path) == expected_sha, 'Offline plan binding')
    plan = json.loads(Path(plan_path).read_text())
    for name, sha in plan['workerFiles'].items():
        require(digest(name) == sha, 'Worker input binding: ' + name)
    root = Path(root)
    require(not (root / 'state.json').exists(), 'Offline analysis refuses overwrite')
    guard = cgroup_limit()
    require(Path('/sys/class/net/lo').exists() and {p.name for p in Path('/sys/class/net').iterdir()} == {'lo'}, 'Worker must have no network interface')
    output = Output(root, plan['outputBytes'] - plan['reservedBytes'], plan['wallSeconds'])
    state = {'status': 'running', 'memoryGuard': guard, 'network': 'none', 'networkRequests': 0,
             'routingQueries': 0, 'originalFeasibilityQualified': False}
    (root / 'state.json').write_bytes(json_bytes(state))
    watchdog = start_watchdog(plan['wallSeconds'])
    try:
        proposal = json.loads(Path('/inputs/proposal.json').read_text())
        data = load_source(plan)
        analyze(plan, output, '/cache/segments.jsonl', proposal, data)
        from coarse_timing_cache_audit import audit
        audit(plan, output, proposal, data)
        state.update(status='offline_analysis_complete_source_incomplete', elapsedSeconds=output.clock() - output.started,
                     outputBytesMetered=output.bytes)
        (root / 'state.json').write_bytes(json_bytes(state))
        return 0
    except Exception as error:
        state.update(status='stopped', errorType=type(error).__name__, error=str(error)[:2000])
        (root / 'state.json').write_bytes(json_bytes(state))
        return 2
    finally:
        if watchdog.poll() is None:
            watchdog.terminate()
            watchdog.wait(timeout=5)


def driver(destination, expected_sha):
    repo = Path(__file__).resolve().parents[1]
    plan_path = repo / EVIDENCE / 'execution-plan.json'
    require(digest(plan_path) == expected_sha, 'Offline execution-plan binding')
    plan = json.loads(plan_path.read_text())
    for name, sha in plan['inputs'].items():
        require(digest(repo / name) == sha, 'Input binding: ' + name)
    root = (repo / destination).resolve()
    require(root == (repo / plan['output']).resolve() and root.is_relative_to(repo / 'data/coarse-quality'), 'Unexpected output path')
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(plan_path.read_bytes())
    name = 'geo-planner-timing-cache-' + uuid.uuid4().hex[:12]
    (root / 'container-name.txt').write_text(name + '\n')
    command = ['docker', 'create', '--pull=never', '--init', '--name', name,
        '--label', 'geo-planner.timing-cache-plan=' + expected_sha, '--network=none', '--read-only',
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=1g', '--memory-swap=1g',
        '--cpus=2', '--pids-limit=64', '--tmpfs=/tmp:rw,size=64m',
        '--mount', f'type=bind,src={repo / "scripts"},dst=/code,readonly',
        '--mount', f'type=bind,src={root},dst=/work',
        '--mount', f'type=bind,src={plan_path},dst=/inputs/plan.json,readonly',
        '--mount', f'type=bind,src={repo / plan["proposal"]},dst=/inputs/proposal.json,readonly',
        '--mount', f'type=bind,src={repo / plan["geometryReport"]},dst=/inputs/geometry-report.json,readonly',
        '--mount', f'type=bind,src={repo / plan["geometryDirectory"]},dst=/geometry,readonly',
        '--mount', f'type=bind,src={repo / plan["cacheDirectory"]},dst=/cache,readonly',
        '--entrypoint=python3', plan['containerImageId'], '-B', '/code/analyze_timing_cache.py',
        '--worker', '/inputs/plan.json', '/work', '--expected-plan-sha', expected_sha]
    identity = None
    try:
        started = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        identity = result.stdout.strip()
        require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Invalid owned container')
        with (root / 'worker.log').open('xb') as log:
            result = subprocess.run(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT,
                timeout=max(1, plan['wallSeconds'] - (time.monotonic() - started)))
        record = json.loads(subprocess.run(['docker', 'inspect', identity], capture_output=True, text=True, check=True, timeout=30).stdout)[0]
        inspection = {'State': record['State'], 'Image': record['Image'],
            'Limits': {k: record['HostConfig'][k] for k in ['Memory', 'MemorySwap', 'ReadonlyRootfs', 'NetworkMode']}}
        (root / 'container-result.json').write_bytes(json_bytes(inspection))
        print(json.dumps({'workerExitCode': result.returncode, 'state': str(root / 'state.json')}, indent=2))
        return result.returncode
    except Exception as error:
        (root / 'driver-failure.json').write_bytes(json_bytes({'error': str(error)[:2000], 'ownedContainer': identity}))
        raise
    finally:
        if identity:
            subprocess.run(['docker', 'rm', '-f', identity], capture_output=True, check=True, timeout=30)
            (root / 'cleanup.json').write_bytes(json_bytes({'ownedContainer': identity, 'removed': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('sha')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--expected-plan-sha')
    args = parser.parse_args()
    raise SystemExit(worker(args.output, args.sha, args.expected_plan_sha) if args.worker else driver(args.output, args.sha))
