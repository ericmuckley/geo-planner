"""One frozen offline diagnostic of captured paths and reference settings."""
from array import array
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import sys
import time

from coarse_backbone_paths import MultiCorridorIndex, account_path, decode_polyline, overlap
from coarse_path_features import CorridorIndex, distance_km, polyline_samples

EVIDENCE = Path('docs/evidence/coarse-backbone-path-audit-2026-10-25')
load = lambda path: json.loads(Path(path).read_text())
def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def ors_references(plan):
    result = {}
    for source in plan['orsBundles']:
        folder = Path(source['path'])
        queries = load(folder/'plan.json')['queries']
        for index, query in enumerate(queries):
            key = source['prefix']+query['id']
            assert key not in result
            body_path = folder/f'{index:02}-response.txt'
            request_path = folder/f'{index:02}-request.json'
            if not body_path.exists() or not request_path.exists():
                result[key] = {'status': 'missing', 'reason': 'Saved response/request missing'}
                continue
            body, request = load(body_path), load(request_path)
            feature = body['features'][0]
            points = feature['geometry']['coordinates']
            assert feature['geometry']['type'] == 'LineString' and len(points) >= 2
            result[key] = {'status': 'available', 'points': points, 'request': request,
                           'metadata': body['metadata'], 'summary': feature['properties']['summary'],
                           'responsePath': str(body_path), 'responseSha256': digest(body_path),
                           'requestPath': str(request_path), 'requestSha256': digest(request_path)}
    return result


def valhalla_references(plan):
    original = load(plan['valhallaOriginal'])
    regional = load(plan['valhallaRegionalSummary'])
    result = {}
    for sample in original['samples']:
        result['original/'+sample['name']] = {
            'status': 'available', 'body': sample['reference'], 'request': sample['request'],
            'engine': original['referenceStatus'], 'sourcePath': plan['valhallaOriginal'],
            'graphProvenanceScope': 'Original saved engine/tile status; no per-route graph identity recorded'}
    for sample in regional['samples']:
        key = 'regional/'+sample['id']
        path = Path(plan['valhallaRegionalDirectory'])/(sample['id']+'.json')
        if not path.exists():
            result[key] = {'status': 'missing', 'reason': 'Saved regional response missing'}
            continue
        record = load(path)
        assert record['status'] == 200
        result[key] = {'status': 'available', 'body': record['body'], 'request': record['request'],
                       'engine': regional['referenceStatus'], 'sourcePath': str(path),
                       'graphProvenanceScope': plan['valhallaRegionalGraphProvenance']}
    return result


def valhalla_geometry(reference):
    trip = reference['body']['trip']
    assert trip['status'] == 0 and trip['units'] == 'kilometers'
    parts = [decode_polyline(leg['shape']) for leg in trip['legs']]
    return parts, trip


def summarize(rows):
    def metric(items, key):
        values = [r[key] for r in items if r.get(key) is not None]
        return {'measured': len(values), 'missing': len(items)-len(values),
                'median': statistics.median(values) if values else None,
                'mean': statistics.fmean(values) if values else None}
    keys = ['detailedCensusTimeShare', 'detailedCensusSourceKm',
            'censusWithin1KmOfOrs', 'censusWithin3KmOfOrs',
            'orsWithin1KmOfCensusSubset', 'orsWithin3KmOfCensusSubset',
            'orsWithin1KmOfValhalla', 'orsWithin3KmOfValhalla',
            'valhallaWithin1KmOfOrs', 'valhallaWithin3KmOfOrs',
            'censusWithin1KmOfValhalla', 'censusWithin3KmOfValhalla',
            'orsMinusValhallaMinutes', 'orsMinusValhallaDistanceKm',
            'orsToValhallaDurationRatio', 'orsToValhallaDistanceRatio']
    groups = {'all': rows, **{name: [r for r in rows if r['set'] == name]
                            for name in ['frontier', 'original', 'regional']}}
    groups['older'] = [r for r in rows if r['set'] != 'frontier']
    return {name: {'planned': len(items), 'metrics': {key: metric(items, key) for key in keys}}
            for name, items in groups.items()}


def run(output, expected_plan):
    started = time.perf_counter()
    plan_path = EVIDENCE/'plan.json'
    assert digest(plan_path) == expected_plan
    plan = load(plan_path)
    assert Path(output).resolve() == Path(plan['output']).resolve()
    for name, expected in plan['inputs'].items():
        assert digest(name) == expected, name
    output = Path(output)
    output.mkdir()  # Never overwrite success, failure or an interrupted run.
    (output/'plan.json').write_bytes(plan_path.read_bytes())
    benchmark = load(plan['benchmark'])
    comparison = load(plan['candidateComparison'])
    captured = json.loads(gzip.decompress(Path(plan['candidatePaths']).read_bytes()))
    cases = {row['id']: row for row in benchmark['cases']}
    paths = {row['id']: row for row in captured}
    measured = {r['set']+'/'+r['id']: r for r in comparison['normalizedRows']}
    assert len(cases) == len(paths) == len(measured) == 83 and set(cases) == set(paths) == set(measured)
    ors, valhalla = ors_references(plan), valhalla_references(plan)
    assert set(ors) == set(cases)
    assert set(valhalla) == {key for key, row in cases.items() if row['valhalla'] is not None}
    graph = load(plan['geometryReport'])
    data = {}
    for name in plan['arrayNames']:
        info = graph['packedArrays'][name]
        raw = gzip.decompress(Path(info['path']).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == info['rawSha256']
        values = array(info['typecode'])
        values.frombytes(raw)
        if sys.byteorder != 'little':
            values.byteswap()
        assert len(values) == info['elements'] and len(raw) == info['rawBytes']
        data[name] = values
    rows, ledger, edge_audits = [], [], []
    inventory = []
    for index, (key, case) in enumerate(cases.items(), 1):
        path = paths[key]
        model = measured[key]
        assert path['origin'] == case['origin'] and path['destination'] == case['destination']
        assert path['pointMinutes'] == model['candidate']['pointMinutes']
        accounting = account_path(path, data, plan['baseCells'])
        costs = accounting['costs']
        row = {'id': key, 'set': case['set'], 'origin': case['origin'], 'destination': case['destination'],
               'orsMinutes': case['ors']['minutes'], 'v9Minutes': model['baseline']['pointMinutes'],
               'candidateMinutes': path['pointMinutes'], 'candidateSignedErrorMinutes': model['candidateErrorMinutes'],
               'costs': costs, 'classes': accounting['classes'],
               'detailedCensusTimeShare': costs['detailedCensusTimeShare'],
               'detailedCensusSourceKm': costs['detailedCensusSourceKm'],
               'detailedEdges': len(accounting['audits'])}
        source_index = MultiCorridorIndex(accounting['parts'], plan['corridor']['indexDegrees'])
        entry = {'id': key, 'candidate': 'captured', 'detailedSourceEdges': len(accounting['audits']),
                 'ors': ors[key]['status'], 'valhalla': valhalla.get(key, {}).get('status', 'not_planned'),
                 'unresolvedGeometry': ['Mixed origin/destination attachment geometry',
                                        'Coarse base-road representative chords'],
                 'sourceSubsetCoverageTimeShare': costs['detailedCensusTimeShare']}
        provider = {'id': key}
        reference = ors[key]
        if reference['status'] == 'available':
            points = reference['points']
            assert abs(reference['summary']['duration']/60-case['ors']['minutes']) < 1e-9
            assert abs(reference['summary']['distance']/1000-case['ors']['distanceKm']) < 1e-9
            coordinates = [[case['origin']['lon'], case['origin']['lat']],
                           [case['destination']['lon'], case['destination']['lat']]]
            assert reference['request']['coordinates'] == coordinates
            metadata = reference['metadata']
            provider['ors'] = {'status': 'available', 'request': reference['request'],
                               'responseQuery': metadata.get('query'), 'engine': metadata.get('engine'),
                               'systemMessage': metadata.get('system_message'),
                               'timestamp': metadata.get('timestamp'),
                               'responsePath': reference['responsePath'], 'responseSha256': reference['responseSha256'],
                               'requestPath': reference['requestPath'], 'requestSha256': reference['requestSha256'],
                               'snapKm': [distance_km(coordinates[0], points[0]), distance_km(coordinates[1], points[-1])],
                               'minutes': reference['summary']['duration']/60,
                               'distanceKm': reference['summary']['distance']/1000, 'vertices': len(points)}
            ors_index = CorridorIndex(points, plan['corridor']['indexDegrees'])
            ors_samples = list(polyline_samples(points, plan['corridor']['sampleStepKm']))
            for radius, fraction in overlap(accounting['samples'], ors_index).items():
                row[f'censusWithin{radius}KmOfOrs'] = fraction
            for radius, fraction in overlap(ors_samples, source_index).items():
                row[f'orsWithin{radius}KmOfCensusSubset'] = fraction
            row['orsPolylineKm'] = math.fsum(weight for _, weight in ors_samples)
        else:
            provider['ors'] = reference
        sensitivity = valhalla.get(key)
        if sensitivity and sensitivity['status'] == 'available':
            parts, trip = valhalla_geometry(sensitivity)
            assert abs(trip['summary']['time']/60-case['valhalla']['minutes']) < 1e-9
            assert abs(trip['summary']['length']-case['valhalla']['distanceKm']) < 1e-9
            expected_locations = [case['origin'], case['destination']]
            assert sensitivity['request']['locations'] == expected_locations
            points = [point for part in parts for point in part]
            summary = trip['summary']
            provider['valhalla'] = {'status': 'available', 'request': sensitivity['request'],
                                    'engine': sensitivity['engine'], 'sourcePath': sensitivity['sourcePath'],
                                    'graphProvenanceScope': sensitivity['graphProvenanceScope'],
                                    'minutes': summary['time']/60, 'distanceKm': summary['length'],
                                    'returnedFlags': {name: summary.get(name) for name in
                                                      ['has_ferry', 'has_toll', 'has_time_restrictions', 'has_highway']},
                                    'snapKm': [distance_km([case['origin']['lon'], case['origin']['lat']], points[0]),
                                               distance_km([case['destination']['lon'], case['destination']['lat']], points[-1])],
                                    'vertices': len(points), 'legs': len(parts)}
            valhalla_index = MultiCorridorIndex(parts, plan['corridor']['indexDegrees'])
            valhalla_samples = [sample for part in parts for sample in polyline_samples(part, plan['corridor']['sampleStepKm'])]
            row['valhallaPolylineKm'] = math.fsum(weight for _, weight in valhalla_samples)
            row['valhallaMinutes'] = summary['time']/60
            for radius, fraction in overlap(accounting['samples'], valhalla_index).items():
                row[f'censusWithin{radius}KmOfValhalla'] = fraction
            if reference['status'] == 'available':
                row['orsMinusValhallaMinutes'] = row['orsMinutes']-row['valhallaMinutes']
                row['orsMinusValhallaDistanceKm'] = provider['ors']['distanceKm']-summary['length']
                row['orsToValhallaDurationRatio'] = row['orsMinutes']/row['valhallaMinutes']
                row['orsToValhallaDistanceRatio'] = provider['ors']['distanceKm']/summary['length']
                for radius, fraction in overlap(ors_samples, valhalla_index).items():
                    row[f'orsWithin{radius}KmOfValhalla'] = fraction
                for radius, fraction in overlap(valhalla_samples, ors_index).items():
                    row[f'valhallaWithin{radius}KmOfOrs'] = fraction
        else:
            provider['valhalla'] = sensitivity or {'status': 'not_planned', 'reason': 'No Valhalla case in the frozen 83/35 protocol'}
        rows.append(row)
        ledger.append(entry)
        inventory.append(provider)
        edge_audits.append({'id': key, 'edges': accounting['audits']})
        print(f'Audited saved paths {index}/83: {key}', file=sys.stderr, flush=True)
    assert len(rows) == len(ledger) == len(inventory) == 83
    counts = lambda values: dict(Counter(values))
    ors_inventory = [row['ors'] for row in inventory if row['ors']['status'] == 'available']
    valhalla_inventory = [row['valhalla'] for row in inventory if row['valhalla']['status'] == 'available']
    timestamps = [row['timestamp'] for row in ors_inventory if row['timestamp'] is not None]
    utc = lambda value: datetime.fromtimestamp(value/1000, timezone.utc).isoformat()
    provider_summary = {'orsAvailable': len(ors_inventory), 'valhallaAvailable': len(valhalla_inventory),
                        'orsRequestPreferences': counts(r['request'].get('preference', 'missing') for r in ors_inventory),
                        'orsResponseQueryPreferences': counts((r['responseQuery'] or {}).get('preference', 'missing') for r in ors_inventory),
                        'orsSystemMessages': counts(r['systemMessage'] or 'missing' for r in ors_inventory),
                        'orsEngineCohorts': counts(json.dumps(r['engine'], sort_keys=True) for r in ors_inventory),
                        'orsCaptureRangeUtc': [utc(min(timestamps)), utc(max(timestamps))] if timestamps else None,
                        'valhallaCostingOptions': counts(json.dumps(r['request'].get('costing_options'), sort_keys=True) for r in valhalla_inventory),
                        'valhallaReturnedFerryFlags': counts(str(r['returnedFlags']['has_ferry']) for r in valhalla_inventory),
                        'valhallaEngineCohorts': counts(json.dumps({k: r['engine'].get(k) for k in
                                                                ['version', 'tileset_last_modified']}, sort_keys=True) for r in valhalla_inventory)}
    checks = {'plannedOrs': 83, 'plannedValhalla': 35, 'allCasesRetained': len(rows) == 83,
              'missingOrs': [r['id'] for r in ledger if r['ors'] != 'available'],
              'missingValhalla': [r['id'] for r in ledger if r['valhalla'] not in ('available', 'not_planned')],
              'detailedSourceEdgesChecked': sum(len(row['edges']) for row in edge_audits),
              'everyPathCostAccounted': True, 'everyDetailedSourceEndpointCostGeometryVerified': True,
              'newRoutingQueries': 0, 'providerRequests': 0, 'runtimeChanged': False}
    report = {'planSha256': expected_plan, 'checks': checks, 'providers': provider_summary,
              'summary': summarize(rows), 'rows': rows, 'missingDataAndCoverageLedger': ledger,
              'providerInventory': inventory, 'sourceGraphProvenance': load(plan['valhallaRegionalGraphProvenance']),
              'elapsedSeconds': time.perf_counter()-started,
              'maxRssBytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024),
              'scope': plan['interpretation']}
    for name, value in [('report.json', report), ('edge-audit.json.gz', edge_audits)]:
        raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
        if name.endswith('.gz'):
            raw = gzip.compress(raw, mtime=0)
        with (output/name).open('xb') as stream:
            stream.write(raw)
    print(json.dumps({'checks': checks, 'providers': provider_summary, 'summary': report['summary'],
                      'elapsedSeconds': report['elapsedSeconds'], 'maxRssBytes': report['maxRssBytes']}, indent=2))


if __name__ == '__main__':
    run(*sys.argv[1:])
