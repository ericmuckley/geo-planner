"""Separate native-response/count/node-closure/identity and capture-ledger audit."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from coarse_osm_records import canonical, strict_json, utc
from coarse_timing_input import PilotError, json_bytes, require


def reference_batch(raw, snapshot, box, caps):
    data = strict_json(raw)
    require(isinstance(data, dict) and type(data.get('version')) in (int, float) and data['version'] == .6, 'Audit response schema')
    require(not {'remark', 'error'} & data.keys(), 'Audit source error')
    require(isinstance(data.get('generator'), str) and data['generator'].startswith('Overpass API ') and len(data['generator']) <= 512, 'Audit generator')
    info = data['osm3s']
    require(utc(info['timestamp_osm_base']) >= utc(snapshot) and isinstance(info.get('copyright'), str) and 0 < len(info['copyright']) <= 4096, 'Audit snapshot/attribution')
    elements = data['elements']
    require(isinstance(elements, list) and elements and sum(e.get('type') == 'count' for e in elements) == 1 and elements[-1]['type'] == 'count', 'Audit terminal count')
    require(len(elements) - 1 <= caps['elementOccurrencesAllWindows'], 'Audit response occurrence cap')
    normalized, counts = {}, Counter()
    for e in elements[:-1]:
        kind, identity = e['type'], e['id']
        require(kind in ('node', 'way', 'relation') and type(identity) is int and identity > 0 and type(e['version']) is int and e['version'] > 0, 'Audit typed identity')
        require('visible' not in e or e['visible'] is True, 'Audit deleted/invisible element')
        require(utc(e['timestamp']) <= utc(snapshot) and len(canonical(e)) <= caps['singleNormalizedElementBytes'], 'Audit element timestamp/size')
        tags = e.get('tags')
        require('tags' not in e or isinstance(tags, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items()), 'Audit native tags')
        record = {k: e[k] for k in ('type', 'id', 'version', 'timestamp')}; record['tags'] = tags
        if 'visible' in e: record['visible'] = e['visible']
        if kind == 'node':
            require(all(type(e[k]) in (int, float) and math.isfinite(e[k]) for k in ('lat', 'lon')), 'Audit coordinates')
            require(-90 <= e['lat'] <= 90 and -180 <= e['lon'] <= 180, 'Audit coordinate range')
            record.update(lat=float(e['lat']), lon=float(e['lon']))
        elif kind == 'way':
            require(isinstance(e.get('nodes'), list) and len(e['nodes']) >= 2 and all(type(i) is int and i > 0 for i in e['nodes']), 'Audit way references')
            require(isinstance(tags, dict) and isinstance(tags.get('highway'), str) and tags['highway'], 'Audit highway selection')
            record['nodes'] = e['nodes']
        else:
            require(isinstance(tags, dict) and tags.get('type') == 'restriction' and isinstance(e.get('members'), list), 'Audit restriction selection')
            require(all(m['type'] in ('node', 'way', 'relation') and type(m['ref']) is int and m['ref'] > 0 and isinstance(m['role'], str) for m in e['members']), 'Audit relation references')
            record['members'] = [{k: m[k] for k in ('type', 'ref', 'role')} for m in e['members']]
        require((kind, identity) not in normalized, 'Audit duplicate response identity')
        normalized[kind, identity] = record; counts[kind + 's'] += 1
    terminal = elements[-1]
    require(type(terminal.get('id')) is int and terminal['id'] == 0, 'Audit count identity')
    tags = terminal['tags']
    require(set(tags) in ({'nodes', 'ways', 'relations', 'total'}, {'nodes', 'ways', 'relations', 'areas', 'total'}), 'Audit count fields')
    require(all(isinstance(v, str) and v.isascii() and v.isdigit() and str(int(v)) == v for v in tags.values()), 'Audit count syntax')
    require(all(int(tags[k]) == counts[k] for k in ('nodes', 'ways', 'relations')) and int(tags['total']) == len(normalized) and int(tags.get('areas', '0')) == 0, 'Audit count agreement')
    needed = {i for e in normalized.values() if e['type'] == 'way' for i in e['nodes']}
    require(needed == {i for kind, i in normalized if kind == 'node'}, 'Audit complete way-node closure')
    rows, external, highways, keys = [], [], Counter(), Counter()
    for key, e in sorted(normalized.items()):
        result = {'snapshotUtc': snapshot, 'element': e, 'elementSha256': hashlib.sha256(canonical(e)).hexdigest()}
        if e['type'] == 'way':
            nodes = [normalized['node', i] for i in e['nodes']]
            hit = False
            for a, b in zip(nodes, nodes[1:]):
                lower, upper = 0., 1.
                for coordinate, lo, hi in [('lon', box[0], box[2]), ('lat', box[1], box[3])]:
                    delta = b[coordinate] - a[coordinate]
                    if delta == 0:
                        if not lo <= a[coordinate] <= hi: upper = -1.; break
                    else:
                        bounds = sorted(((lo - a[coordinate]) / delta, (hi - a[coordinate]) / delta))
                        lower, upper = max(lower, bounds[0]), min(upper, bounds[1])
                hit |= lower <= upper
            require(hit, 'Audit selected geometry misses bbox')
            result['geometryDependencySha256'] = hashlib.sha256(canonical([snapshot, nodes])).hexdigest()
            highways[e['tags']['highway']] += 1; keys.update(e['tags'].keys())
        if e['type'] == 'relation':
            require(any((m['type'], m['ref']) in normalized for m in e['members']), 'Audit unrelated restriction')
            external.extend({'relationId': e['id'], **m} for m in e['members'] if (m['type'], m['ref']) not in normalized)
        rows.append(result)
    return {'generator': data['generator'], 'sourceBaseTimestamp': info['timestamp_osm_base'], 'copyright': info['copyright'],
        'records': rows, 'counts': {k: counts[k] for k in ('nodes', 'ways', 'relations')},
        'externalRestrictionMemberCount': len(external), 'externalRestrictionMembersSha256': hashlib.sha256(canonical(external)).hexdigest(),
        'rawHighwayCounts': dict(highways), 'wayTagKeyOccurrences': dict(keys)}


def audit(proposal, queries, root):
    root = Path(root); state = strict_json((root / 'state.json').read_bytes()); caps = proposal['hardCaps']
    require(state['snapshotUtc'] == proposal['source']['snapshotUtc'], 'Audit requested snapshot binding')
    require([w['id'] for w in state['windows']] == [q['id'] for q in queries], 'Audit all window statuses/order')
    require(state['sourceAdapterImplemented'] is False and state['originalFeasibilityQualified'] is False and state['routingProviderRequests'] == 0, 'Audit no permission/model admission')
    expected_sequence = [(kind, q) for q in queries for kind in ('status', 'query')]
    require(len(state['http']) <= caps['httpAttempts'] and len(state['http']) <= len(expected_sequence), 'Audit request cap')
    byte_count, valid_occurrences, expected_rows, seen, complete_unique, totals = 0, 0, [], {}, 0, Counter()
    reports_bytes, generators = 0, set()
    for number, (event, (kind, query)) in enumerate(zip(state['http'], expected_sequence), 1):
        require(event['number'] == number and (event['kind'], event['windowId']) == (kind, query['id']), 'Audit attempt sequence')
        require(event['method'] == ('GET' if kind == 'status' else 'POST') and event['url'] == proposal['source']['statusUrl' if kind == 'status' else 'queryUrl'], 'Audit endpoint/method')
        require(event['formBodySha256'] == (None if kind == 'status' else query['formBodySha256']), 'Audit frozen query hash')
        require(event['bodyFile'] == f'http/{number:05d}.bin', 'Audit raw response path')
        raw = (root / event['bodyFile']).read_bytes(); byte_count += len(raw)
        require(len(raw) == event['receivedBodyBytes'] and hashlib.sha256(raw).hexdigest() == event['bodySha256'], 'Audit every received-body byte/hash')
        limit = caps['statusAcceptedBodyBytes' if kind == 'status' else 'queryAcceptedBodyBytes']
        require(len(raw) <= limit + 1 and event['finishedElapsedSeconds'] >= event['startedElapsedSeconds'], 'Audit response bounds')
        if event['outcome'] == 'complete':
            require(event['status'] == 200 and len(raw) <= limit, 'Audit accepted HTTP response')
            require(0 < event['absoluteTimeoutSeconds'] <= proposal['timeouts']['statusAbsoluteClientSeconds' if kind == 'status' else 'queryAbsoluteClientSeconds'], 'Audit request deadline bound')
            require(event['finishedElapsedSeconds'] - event['startedElapsedSeconds'] < event['absoluteTimeoutSeconds'], 'Audit absolute deadline')
            headers = event['headers']; require(headers.get('content-encoding', 'identity').lower().strip() in ('identity', ''), 'Audit encoding')
            if 'content-length' in headers: require(int(headers['content-length']) == len(raw), 'Audit framing length')
            if kind == 'query': require(headers.get('content-type', '').split(';')[0].strip().lower() == 'application/json', 'Audit query content type')
        if kind == 'status':
            if number < len(state['http']):
                require(event['outcome'] == 'complete', 'Audit query after failed status')
                text = raw.decode('utf-8')
                now = re.findall(r'^Current time: (\S+)\s*$', text, re.M)
                rate = re.findall(r'^Rate limit: (\d+)\s*$', text, re.M)
                require(len(now) == len(rate) == 1 and int(rate[0]) > 0 and utc(now[0]) >= utc(state['snapshotUtc']), 'Audit status metadata')
                available = re.findall(r'^(\d+) slots? available now\.\s*$', text, re.M)
                require(len(available) <= 1, 'Audit status availability')
                if available and int(available[0]) > 0:
                    require(int(available[0]) <= int(rate[0]), 'Audit slot count'); wait = 0.
                else:
                    slots = re.findall(r'^Slot available after: (\S+), in (\d+) seconds?\.\s*$', text, re.M)
                    require(slots, 'Audit status slot time')
                    waits = [(utc(at) - utc(now[0])).total_seconds() for at, _ in slots]
                    require(all(t >= 0 and abs(t - int(s[1])) <= 1 for t, s in zip(waits, slots)), 'Audit status wait syntax')
                    wait = min(waits)
                require(wait <= proposal['timeouts']['maximumStatusDirectedWaitSeconds'], 'Audit status wait cap')
                window = next(w for w in state['windows'] if w['id'] == query['id'])
                require(window['statusWaitSeconds'] == wait and state['http'][number]['startedElapsedSeconds'] - event['finishedElapsedSeconds'] >= wait - 1e-6, 'Audit honored status wait')
            continue
        window = next(w for w in state['windows'] if w['id'] == query['id'])
        try: result = reference_batch(raw, state['snapshotUtc'], query['bbox'], caps) if event['outcome'] == 'complete' else None
        except (PilotError, ValueError, KeyError, TypeError): result = None
        if result is not None and state['sourceGenerator'] is not None and result['generator'] != state['sourceGenerator']: result = None
        if result is None:
            require(window['status'] != 'capture_complete', 'Audit complete window has invalid response'); continue
        valid_occurrences += len(result['records'])
        conflict = any((r['element']['type'], r['element']['id']) in seen and seen[r['element']['type'], r['element']['id']] != r for r in result['records'])
        if conflict:
            require(window['status'] != 'capture_complete', 'Audit conflicting source/dependency identity'); continue
        new_count = 0
        for record in result['records']:
            key = record['element']['type'], record['element']['id']
            if key not in seen:
                seen[key] = record; expected_rows.append({'firstWindowId': query['id'], **record}); new_count += 1
        if window['status'] == 'capture_complete':
            complete_unique = len(expected_rows); totals.update(result['counts']); generators.add(result['generator'])
            require(window['reportPath'] == 'windows/' + query['id'] + '.json', 'Audit window report path')
            report_path = root / window['reportPath']; encoded = report_path.read_bytes(); reports_bytes += len(encoded)
            require(hashlib.sha256(encoded).hexdigest() == window['reportSha256'], 'Audit window report binding')
            report = strict_json(encoded)
            expected = {k: v for k, v in result.items() if k != 'records'}
            expected.update(id=query['id'], status='capture_complete', newUniqueElements=new_count,
                sourceFeasibilityQualified=False, physicalIdentityVerified=False, carAccessVerified=False)
            require(report == expected and window['counts'] == result['counts'], 'Audit raw inventory/count/dependency summary')
            require(window['newUniqueElements'] == new_count and window['sourceBaseTimestamp'] == result['sourceBaseTimestamp'] and window['copyright'] == result['copyright'], 'Audit window source identity')
    with (root / 'elements.jsonl').open('rb') as stream: encoded_rows = list(stream)
    require({str(p.relative_to(root)) for p in (root / 'http').glob('*.bin')} == {e['bodyFile'] for e in state['http']}, 'Audit raw-body roster')
    rows = [strict_json(line) for line in encoded_rows]
    require(rows == expected_rows[:len(rows)] and complete_unique <= len(rows) <= caps['uniqueSourceElementsAllTypes'], 'Audit normalized complete prefix')
    require(all(len(line) <= caps['singleNormalizedElementBytes'] for line in encoded_rows), 'Audit normalized element cap')
    budget = state['budget']; extract_bytes = sum(map(len, encoded_rows))
    require(budget['receivedHttpBodyBytes'] == byte_count <= caps['totalHttpBodyBytes'] and budget['httpAttempts'] == len(state['http']), 'Audit aggregate HTTP accounting')
    require(budget['uniqueNormalizedElements'] == len(rows) and budget['normalizedExtractBytes'] == extract_bytes <= caps['normalizedExtractBytes'], 'Audit retained element accounting')
    require(budget['validatedElementOccurrences'] == valid_occurrences, 'Audit validated occurrence accounting')
    require(budget['accountedWorkingBytes'] + budget['reservedTmpBytes'] + budget['reservedStateDriverBytes'] <= caps['workingBytes'], 'Audit working-file bound')
    complete = state['status'] == 'captured_all_windows_analysis_pending'
    if complete:
        require(all(w['status'] == 'capture_complete' for w in state['windows']) and len(state['http']) == len(expected_sequence), 'Audit complete-window ledger')
        require(len(rows) == len(expected_rows) and len(generators) == 1 and state['sourceGenerator'] in generators and state['totals'] == totals, 'Audit completed source identity/totals')
        require(valid_occurrences <= caps['elementOccurrencesAllWindows'], 'Audit occurrence cap')
        require({str(p.relative_to(root)) for p in (root / 'windows').glob('*.json')} == {w['reportPath'] for w in state['windows']}, 'Audit window report roster')
        require(budget['accountedWorkingBytes'] == budget['initialWorkingBytes'] + byte_count + extract_bytes + reports_bytes, 'Audit full working-file accounting')
    else:
        require(state['status'] == 'stopped' and budget['stopped'] and all(w['status'] in ('capture_complete', 'incomplete_after_stop', 'unmeasured_after_stop') for w in state['windows']), 'Audit stopped/remaining windows')
        statuses = [w['status'] for w in state['windows']]
        first = next((i for i, s in enumerate(statuses) if s != 'capture_complete'), len(statuses))
        require(first == len(statuses) or statuses[first] in ('incomplete_after_stop', 'unmeasured_after_stop') and all(s == 'unmeasured_after_stop' for s in statuses[first + 1:]), 'Audit stopped window prefix')
    result = {'independentRawBodiesCountsClosureTypedIdentityAndLedgerAudit': True, 'captureComplete': complete,
        'windows': len(queries), 'completedWindows': sum(w['status'] == 'capture_complete' for w in state['windows']),
        'receivedHttpBodyBytes': byte_count, 'httpAttempts': len(state['http']), 'uniqueNormalizedElements': len(rows),
        'validatedElementOccurrences': valid_occurrences, 'sourceAdapterImplemented': False, 'originalFeasibilityQualified': False,
        'method': 'Separate native-field/count/closure/dependency reconstruction and exact normalized prefix/body/ledger checks. Shared JSON/time/hash primitives only; no source permission, usable-limit, matcher or model proof.'}
    encoded = json_bytes(result); require(len(encoded) < 1024 ** 2, 'Audit result cap')
    with (root / 'audit.json').open('xb') as stream: stream.write(encoded)
    return result
