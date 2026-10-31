"""Bounded Parquet input and geometry matching for the isolated timing pilot."""
from array import array
import base64
import bisect
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import struct
import sys
import zipfile

from coarse_timing_input import PilotError, RangeFile, digest, json_bytes, require, usable_limit
from coarse_backbone_paths import arc_geometry
from coarse_path_features import distance_km, segment_distance_km


def intersects(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def clip_segment(a, b, box):
    start, end = 0., 1.
    for axis in (0, 1):
        delta = b[axis] - a[axis]
        if delta == 0:
            if not box[axis] <= a[axis] <= box[axis + 2]:
                return None
            continue
        lo, hi = sorted(((box[axis] - a[axis]) / delta, (box[axis + 2] - a[axis]) / delta))
        start, end = max(start, lo), min(end, hi)
        if end <= start:
            return None
    return start, end


def interpolate(a, b, t):
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]


def angle_degrees(a, b, c, d):
    scale = math.cos(math.radians((a[1] + b[1] + c[1] + d[1]) / 4))
    x, y = ((b[0] - a[0]) * scale, b[1] - a[1]), ((d[0] - c[0]) * scale, d[1] - c[1])
    product = math.hypot(*x) * math.hypot(*y)
    if not product:
        return 180.
    # Source geometry is undirected; compare either travel orientation.
    return math.degrees(math.acos(min(1., abs(sum(i * j for i, j in zip(x, y))) / product)))


def decode_lines(raw):
    require(isinstance(raw, bytes) and len(raw) <= 16 * 1024 ** 2, 'Geometry byte allocation cap/type')
    offset = 0
    def geometry():
        nonlocal offset
        require(offset + 5 <= len(raw), 'Truncated WKB')
        endian = '<' if raw[offset] == 1 else '>' if raw[offset] == 0 else None
        require(endian, 'WKB byte order')
        kind = struct.unpack_from(endian + 'I', raw, offset + 1)[0]
        offset += 5
        dims = 2 + bool(kind & 0x80000000) + bool(kind & 0x40000000)
        if kind & 0x20000000:
            require(offset + 4 <= len(raw), 'Truncated SRID')
            require(struct.unpack_from(endian + 'I', raw, offset)[0] in (0, 4326), 'Unsupported SRID')
            offset += 4
        base = kind & 0x0fffffff
        dims += (base // 1000 in (1, 2)) + 2 * (base // 1000 == 3)
        base %= 1000
        require(offset + 4 <= len(raw), 'Truncated WKB count')
        count = struct.unpack_from(endian + 'I', raw, offset)[0]
        offset += 4
        require(count <= 250000, 'Geometry point/count cap')
        if base == 5:
            result = []
            for _ in range(count):
                result.extend(geometry())
            return result
        require(base == 2 and count >= 2 and offset + count * dims * 8 <= len(raw), 'Unsupported/truncated LineString')
        result = []
        for _ in range(count):
            point = list(struct.unpack_from(endian + 'd' * dims, raw, offset)[:2])
            offset += dims * 8
            require(all(math.isfinite(v) for v in point) and -180 <= point[0] <= 180 and -90 <= point[1] <= 90, 'Invalid geometry coordinate')
            result.append(point)
        return [result]
    lines = geometry()
    require(offset == len(raw), 'Trailing WKB bytes')
    return lines


def row_group_boxes(metadata, columns):
    result = []
    for index in range(metadata.num_row_groups):
        group = metadata.row_group(index)
        values = {}
        for i in range(group.num_columns):
            column = group.column(i)
            if column.path_in_schema in columns and column.statistics and column.statistics.has_min_max:
                values[column.path_in_schema] = column.statistics
        if len(values) != 4:
            result.append(None)  # Missing stats cannot justify skipping any row group.
        else:
            box = [values['bbox.xmin'].min, values['bbox.ymin'].min,
                   values['bbox.xmax'].max, values['bbox.ymax'].max]
            require(all(isinstance(v, (int, float)) and math.isfinite(v) for v in box) and box[0] <= box[2] and box[1] <= box[3], 'Invalid spatial row-group stats')
            result.append(box)
    return result


def install_arrow(budget, meter):
    require(sys.version_info[:2] == (3, 13) and platform.machine() == 'aarch64', 'Pinned wheel platform differs')
    raw, _ = meter.get('https://pypi.org/pypi/pyarrow/21.0.0/json', limit=2 * 1024 ** 2, tool=True)
    metadata = json.loads(raw)
    candidates = [r for r in metadata['urls'] if r['filename'] == 'pyarrow-21.0.0-cp313-cp313-manylinux_2_28_aarch64.whl']
    require(len(candidates) == 1 and not candidates[0].get('yanked'), 'Pinned wheel unavailable; no fallback')
    lock = candidates[0]
    budget.write('tool-lock.json', json_bytes({'version': '21.0.0', 'url': lock['url'], 'bytes': lock['size'], 'sha256': lock['digests']['sha256']}))
    raw, _ = meter.get(lock['url'], limit=lock['size'], tool=True)
    require(len(raw) == lock['size'] and hashlib.sha256(raw).hexdigest() == lock['digests']['sha256'], 'Wheel identity changed')
    budget.write('tools/pyarrow.whl', raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(sum(i.file_size for i in archive.infolist()) <= 512 * 1024 ** 2, 'Tool extraction cap')
        for info in archive.infolist():
            if info.is_dir():
                continue
            require(not info.filename.startswith('/') and '..' not in Path(info.filename).parts and
                    (info.external_attr >> 16) & 0o170000 != 0o120000, 'Unsafe wheel path/link')
            require(info.file_size <= 256 * 1024 ** 2, 'Tool file allocation cap')
            budget.write('tools/site/' + info.filename, archive.read(info))
    sys.path.insert(0, str(budget.root / 'tools/site'))
    import pyarrow as pa
    import pyarrow.parquet as pq
    require(pa.__version__ == '21.0.0', 'Tool import identity')
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    # Exercise the real Parquet engine through our file-like ranged boundary.
    table = pa.table({'bbox': [{'xmin': 0., 'ymin': 0., 'xmax': 1., 'ymax': 1.}], 'value': [7]})
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    fixture = buffer.getvalue()
    class LocalRanges:
        def get(self, url, **kwargs):
            text = kwargs['headers']['Range'].split('=')[1]
            start, end = map(int, text.split('-'))
            return fixture[start:end + 1], {}
    with RangeFile(LocalRanges(), {'url': 'https://fixture.invalid/fixture', 'bytes': len(fixture), 'etag': 'fixture'}) as source:
        parquet = pq.ParquetFile(source, pre_buffer=False, buffer_size=0)
        require(parquet.read(columns=['value']).to_pylist() == [{'value': 7}], 'Real Parquet range integration failed')
        require(row_group_boxes(parquet.metadata, {'bbox.xmin', 'bbox.ymin', 'bbox.xmax', 'bbox.ymax'}) == [[0., 0., 1., 1.]], 'Real bbox-stat integration failed')
        parquet.close()
    budget.write('parquet-selftest.json', json_bytes({'version': pa.__version__, 'realRangedReadPassed': True, 'bboxStatisticsPassed': True}))
    return pq


def load_source(plan):
    report = json.loads(Path('/inputs/geometry-report.json').read_text())
    require(digest('/inputs/geometry-report.json') == plan['geometryReportSha256'], 'Cached geometry report binding')
    names = ['nodeCoordinates', 'arcFrom', 'arcTo', 'arcRoadKm', 'arcSpeedKph', 'arcByteOffsets', 'arcInteriorOffsets',
             'interiorSourceKm', 'geometryBytes', 'cellIds', 'cellArcOffsets', 'cellArcs']
    data = {}
    for name in names:
        info = report['packedArrays'][name]
        path = Path('/geometry') / Path(info['path']).name
        require(digest(path) == info['sha256'], 'Source array binding: ' + name)
        raw = gzip.decompress(path.read_bytes())
        require(len(raw) == info['rawBytes'] and hashlib.sha256(raw).hexdigest() == info['rawSha256'], 'Decoded array binding')
        values = array(info['typecode'])
        values.frombytes(raw)
        if sys.byteorder != 'little':
            values.byteswap()
        data[name] = values
    return data


def source_spans(data, grid, box):
    west, south = grid['bounds'][:2]
    candidates = set()
    for y in range(max(0, math.floor((box[1] - south) / grid['step']) - 1), min(grid['height'], math.floor((box[3] - south) / grid['step']) + 2)):
        for x in range(max(0, math.floor((box[0] - west) / grid['step']) - 1), min(grid['width'], math.floor((box[2] - west) / grid['step']) + 2)):
            cell = y * grid['width'] + x
            index = bisect.bisect_left(data['cellIds'], cell)
            if index < len(data['cellIds']) and data['cellIds'][index] == cell:
                candidates.update(data['cellArcs'][data['cellArcOffsets'][index]:data['cellArcOffsets'][index + 1]])
    result = []
    for arc in sorted(candidates):
        points, cumulative = arc_geometry(data, arc)
        spans = []
        for i, (a, b) in enumerate(zip(points, points[1:])):
            clipped = clip_segment(a, b, box)
            if clipped:
                lo, hi = clipped
                weight = (cumulative[i + 1] - cumulative[i]) * (hi - lo)
                if weight > 0:
                    spans.append((interpolate(a, b, lo), interpolate(a, b, hi), weight))
        if spans:
            result.append((arc, spans))
    return result


class MatchIndex:
    def __init__(self, rows, box):
        self.rows, self.segments, self.bins = rows, [], defaultdict(list)
        for index, row in enumerate(rows):
            for line in row['_lines']:
                for a, b in zip(line, line[1:]):
                    clipped = clip_segment(a, b, box)
                    if not clipped:
                        continue
                    a, b = interpolate(a, b, clipped[0]), interpolate(a, b, clipped[1])
                    padding = .025 / (110 * math.cos(math.radians(max(abs(a[1]), abs(b[1])))))
                    sid = len(self.segments)
                    self.segments.append((index, a, b))
                    for x in range(math.floor((min(a[0], b[0]) - padding) / .01), math.floor((max(a[0], b[0]) + padding) / .01) + 1):
                        for y in range(math.floor((min(a[1], b[1]) - padding) / .01), math.floor((max(a[1], b[1]) + padding) / .01) + 1):
                            self.bins[x, y].append(sid)

    def match(self, spans):
        weight = sum(s[2] for s in spans)
        covered = defaultdict(float)
        for a, b, km in spans:
            count = max(1, math.ceil(distance_km(a, b) / .025))
            for i in range(count):
                point = interpolate(a, b, (i + .5) / count)
                found = set()
                for sid in self.bins.get((math.floor(point[0] / .01), math.floor(point[1] / .01)), []):
                    index, c, d = self.segments[sid]
                    if angle_degrees(a, b, c, d) <= 15 and segment_distance_km(point, c, d) <= .025:
                        found.add(index)
                for index in found:
                    covered[index] += km / count
        candidates = [(index, min(1., km / weight)) for index, km in covered.items() if km / weight >= .8 - 1e-12]
        if len(candidates) != 1:
            return {'status': 'ambiguous' if candidates else 'unmatched', 'sourceKm': weight, 'usableKm': 0., 'candidateCount': len(candidates)}
        index, fraction = candidates[0]
        row = self.rows[index]
        return {'status': 'plausible_' + row['_limit']['status'], 'sourceKm': weight,
                'usableKm': weight * fraction if row['_limit']['status'] == 'usable' else 0.,
                'candidateCount': 1, 'fraction': fraction, 'overtureId': row['id'], 'version': row['version'],
                'class': row['class'], 'limit': row['_limit'], 'gradeAndRoadIdentity': 'unverified'}


def serializable(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    raise TypeError('Unsupported source scalar: ' + type(value).__name__)


def capture(plan, proposal, objects, budget, meter, state, checkpoint):
    pq = install_arrow(budget, meter)
    windows = proposal['selection']['windows']
    records, memberships, schemas = {}, defaultdict(set), set()
    extracted = budget.root / 'segments.jsonl'
    require(not extracted.exists(), 'Extract refuses overwrite')
    # Flush each retained record through the budget so failed runs keep their
    # partial extract, including records preceding a later transport failure.
    for object_index, record in enumerate(objects):
        budget.check()
        state.update(stage='parquet_read', objectsInspected=object_index)
        checkpoint()
        with RangeFile(meter, record) as source:
            parquet = pq.ParquetFile(source, pre_buffer=False, buffer_size=0,
                thrift_string_size_limit=16 * 1024 ** 2, thrift_container_size_limit=1024 ** 2)
            schema = parquet.schema_arrow.remove_metadata()
            fingerprint = hashlib.sha256(schema.serialize().to_pybytes()).hexdigest()
            if not schemas:
                require(set(proposal['columns']).issubset(schema.names), 'Required source columns missing')
                budget.write('source-schema.json', json_bytes({'sha256': fingerprint, 'schema': str(schema), 'publisherSchemaClaim': proposal['source']['proposedSchema']}))
            schemas.add(fingerprint)
            require(len(schemas) == 1, 'Publisher schemas differ; no fallback')
            boxes = row_group_boxes(parquet.metadata, {'bbox.xmin', 'bbox.ymin', 'bbox.xmax', 'bbox.ymax'})
            for group_index, box in enumerate(boxes):
                if box is not None and not any(intersects(box, w['bbox']) for w in windows):
                    continue
                for batch in parquet.iter_batches(batch_size=512, row_groups=[group_index], columns=proposal['columns'], use_threads=False):
                    budget.check()
                    for row in batch.to_pylist():
                        if row.get('subtype') != 'road':
                            continue
                        bounds = row.get('bbox')
                        require(isinstance(bounds, dict) and all(math.isfinite(bounds[k]) for k in ['xmin', 'ymin', 'xmax', 'ymax']), 'Malformed segment bbox')
                        hit = [w['id'] for w in windows if intersects([bounds['xmin'], bounds['ymin'], bounds['xmax'], bounds['ymax']], w['bbox'])]
                        if not hit:
                            continue
                        key = (row['id'], row['version'])
                        require(isinstance(key[0], str) and isinstance(key[1], int) and not isinstance(key[1], bool), 'Missing segment identity')
                        geometry = bytes(row.pop('geometry'))
                        row['geometryWkbBase64'] = base64.b64encode(geometry).decode()
                        raw = (json.dumps(row, default=serializable, separators=(',', ':'), sort_keys=True, allow_nan=False) + '\n').encode()
                        source_sha = hashlib.sha256(raw).hexdigest()
                        if key not in records:
                            require(budget.rows < proposal['hardCaps']['uniqueSegmentRows'], 'Unique-row cap')
                            budget.append('segments.jsonl', raw, proposal['hardCaps']['retainedExtractBytes'])
                            row['_sourceSha256'] = source_sha
                            row['_limit'] = usable_limit(row)
                            try:
                                row['_lines'] = decode_lines(geometry)
                            except PilotError:
                                row['_lines'] = []
                                row['_limit'] = {'status': 'malformed_geometry', 'kmh': None}
                            records[key] = row
                            budget.rows += 1
                        else:
                            require(source_sha == records[key]['_sourceSha256'], 'Conflicting duplicate segment identity')
                        for wid in hit:
                            memberships[wid].add(key)
                    checkpoint()
            parquet.close()
    if not extracted.exists():
        budget.write('segments.jsonl', b'')
    data = load_source(plan)
    results, reviews = [], {}
    for index, window in enumerate(windows):
        budget.check()
        state.update(stage='source_match', windowIndex=index)
        checkpoint()
        selected = [records[key] for key in sorted(memberships[window['id']])]
        matcher = MatchIndex(selected, window['bbox'])
        matches = []
        for arc, spans in source_spans(data, plan['grid'], window['bbox']):
            budget.check()
            match = matcher.match(spans)
            match.update(arc=arc, windowId=window['id'], sourceClassKph=int(data['arcSpeedKph'][arc]))
            matches.append(match)
            if match['candidateCount'] == 1:
                rank = hashlib.sha256(f'{proposal["source"]["proposedRelease"]}/{match["overtureId"]}/{window["id"]}'.encode()).hexdigest()
                review = reviews.setdefault(rank, {'rank': rank, 'overtureId': match['overtureId'], 'windowId': window['id'], 'sourceMatches': []})
                review['sourceMatches'].append({'match': match, 'sourceSpans': spans})
        source_km = sum(m['sourceKm'] for m in matches)
        usable_km = sum(m['usableKm'] for m in matches)
        counts = dict(Counter(row['_limit']['status'] for row in selected))
        classes = {}
        for row in selected:
            group = classes.setdefault(row['class'], {'bboxCandidateRows': 0, 'geometryKm': 0., 'limitStatusCounts': Counter(), 'limitGeometryKm': defaultdict(float)})
            km = 0.
            for line in row['_lines']:
                for a, b in zip(line, line[1:]):
                    clipped = clip_segment(a, b, window['bbox'])
                    if clipped:
                        km += distance_km(interpolate(a, b, clipped[0]), interpolate(a, b, clipped[1]))
            group['bboxCandidateRows'] += 1
            group['geometryKm'] += km
            group['limitStatusCounts'][row['_limit']['status']] += 1
            group['limitGeometryKm'][row['_limit']['status']] += km
        source_classes = {str(speed): {'sourceKm': sum(m['sourceKm'] for m in matches if m['sourceClassKph'] == speed),
            'usableKm': sum(m['usableKm'] for m in matches if m['sourceClassKph'] == speed)} for speed in (85, 105)}
        result = {'id': window['id'], 'segmentRows': len(selected), 'limitStatusCounts': counts,
                  'sourceKm': source_km, 'usableKm': usable_km,
                  'usableFraction': usable_km / source_km if source_km else None,
                  'matchStatusCounts': dict(Counter(m['status'] for m in matches)), 'sourceClassesKph': source_classes,
                  'publisherClasses': classes, 'matches': matches}
        results.append(result)
        budget.write('windows/' + window['id'] + '.json', json_bytes(result))
        state['windows'][index]['status'] = 'data_complete_review_pending'
        checkpoint()
    selected_reviews = [reviews[key] for key in sorted(reviews)[:50]]
    budget.write('review-selection.json', json_bytes(selected_reviews))
    source_km = sum(r['sourceKm'] for r in results)
    usable_km = sum(r['usableKm'] for r in results)
    summary = {'windows': len(results), 'sourceKm': source_km, 'usableKm': usable_km,
               'usableFraction': usable_km / source_km if source_km else None,
               'coverageScreenPassed': bool(source_km and usable_km / source_km >= .5),
               'independentMatchReviewPending': len(selected_reviews), 'feasibilityPassed': False,
               'naturalEarthBase': {'status': 'unresolved_source_alignment', 'includedInPrimaryDenominator': False},
               'scope': 'No ETA or nationwide/road-identity claim; no model changes. Detailed Census km counted per window membership, including overlapping windows.'}
    budget.write('report.json', json_bytes({'summary': summary, 'windowResults': results, 'budget': budget.snapshot()}))
    return summary
