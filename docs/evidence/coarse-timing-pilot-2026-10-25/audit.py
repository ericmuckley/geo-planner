"""Read-only audit of the stopped capture; no importer, decoder or network call."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
plan = load(folder / 'analysis-plan.json')
for name, expected in plan['inputs'].items():
    assert digest(repo / name) == expected, name
execution = load(folder / 'execution-plan.json')
root = repo / execution['output']
proposal = load(repo / execution['proposal'])
state = load(root / 'state.json')
caps = proposal['hardCaps']
assert state['status'] == 'stopped' and state['stage'] == 'parquet_read'
assert len(state['windows']) == 21
assert [w['id'] for w in state['windows']] == [w['id'] for w in proposal['selection']['windows']]
assert all(w['status'] == 'unmeasured_after_stop' for w in state['windows'])
events = state['network']
assert [e['requestNumber'] for e in events] == list(range(1, len(events) + 1))
assert len(events) == state['budget']['httpRequests'] <= caps['httpRequests']
assert all(e['outcome'] == 'complete' for e in events[:-1]) and events[-1]['outcome'] == 'failed'
assert events[-1]['status'] is None and events[-1]['receivedBodyBytes'] == 0
received = tool_received = 0
manifest = load(root / 'object-manifest.json')
urls = {r['url'] for r in manifest['objects']}
assert len(urls) == len(manifest['objects']) == 128
for event in events:
    host = urlsplit(event['url']).hostname
    assert host in execution['allowedHosts']
    path = (root / event['bodyFile']).resolve()
    assert path.is_relative_to(root.resolve())
    assert path.stat().st_size == event['receivedBodyBytes']
    assert digest(path) == event['bodySha256']
    received += event['receivedBodyBytes']
    if host in ('pypi.org', 'files.pythonhosted.org'):
        tool_received += event['receivedBodyBytes']
    if event['status'] == 206:
        assert event['url'] in urls
assert received == state['budget']['receivedHttpBodyBytes'] <= caps['receivedHttpBodyBytes']
assert tool_received == state['budget']['toolBodyBytes'] <= caps['toolDownloadBodyBytesWithinTotal']
selftest = load(root / 'parquet-selftest.json')
assert selftest['realRangedReadPassed'] and selftest['bboxStatisticsPassed']
tool = load(root / 'tool-lock.json')
assert digest(root / 'tools/pyarrow.whl') == tool['sha256'] and tool['version'] == '21.0.0'
assert (root / 'tools/pyarrow.whl').stat().st_size == tool['bytes']
rows, keys = 0, set()
window_counts = {w['id']: 0 for w in proposal['selection']['windows']}
with (root / 'segments.jsonl').open() as stream:
    for line in stream:
        row = json.loads(line)
        key = (row['id'], row['version'])
        assert key not in keys
        keys.add(key)
        assert set(proposal['columns']) - {'geometry'} <= set(row)
        assert 'geometryWkbBase64' in row and row['subtype'] == 'road'
        box = row['bbox']
        hits = []
        for window in proposal['selection']['windows']:
            west, south, east, north = window['bbox']
            if box['xmin'] <= east and box['xmax'] >= west and box['ymin'] <= north and box['ymax'] >= south:
                hits.append(window['id'])
                window_counts[window['id']] += 1
        assert hits
        rows += 1
assert rows == state['budget']['uniqueRows'] <= caps['uniqueSegmentRows']
extract_bytes = (root / 'segments.jsonl').stat().st_size
assert extract_bytes <= caps['retainedExtractBytes']
working = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
assert working + 64 * 1024 ** 2 <= caps['totalLocalWorkingBytes']
container = load(root / 'container-result.json')
assert not container['State']['OOMKilled'] and container['State']['ExitCode'] == 2
assert container['Image'] == execution['containerImageId']
assert container['Limits']['Memory'] == container['Limits']['MemorySwap'] == caps['processRssBytes']
assert container['Limits']['ReadonlyRootfs']
assert state['memoryGuard'] == {'memoryMaxBytes': caps['processRssBytes'], 'swapMaxBytes': 0}
assert state['budget']['elapsedSeconds'] < caps['wallSeconds']
assert not (root / 'report.json').exists() and not (root / 'review-selection.json').exists()
result = {'independentCaptureBudgetIdentityAndPartialRowAudit': True,
          'status': 'source_timeout_stopped_no_retry', 'receivedHttpBodyBytes': received,
          'toolBodyBytes': tool_received, 'httpRequests': len(events), 'retainedUniqueRoadRows': rows,
          'extractBytes': extract_bytes, 'workingFilesBytes': working,
          'boundedWorkingBytesIncludingMaximumTmp': working + 64 * 1024 ** 2,
          'objectsInFrozenManifest': len(urls), 'currentObjectIndex': state['objectsInspected'],
          'plannedWindows': 21, 'completedWindows': 0, 'windowStatuses': state['windows'],
          'retainedBboxCandidateRowsByWindow': window_counts,
          'coverageMatchingAndReviewPerformed': False, 'feasibilityQualified': False,
          'sourceSchemaFingerprint': load(root / 'source-schema.json')['sha256'],
          'scope': 'Partial byte/identity/row accounting only. Bbox candidate counts are not geometry or timing/matching coverage. Live response headers were checked by frozen code but are not separately retained for header replay. No new data, retries, feature fit or candidate.'}
with (folder / 'analysis.json').open('x') as stream:
    stream.write(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ['windowStatuses', 'retainedBboxCandidateRowsByWindow']}, indent=2))
