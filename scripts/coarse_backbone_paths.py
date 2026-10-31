"""Pure saved-path geometry/accounting helpers; never compute a routing query."""
from collections import defaultdict
import hashlib
import json
import math

from coarse_backbone_codec import decode_signed32
from coarse_path_features import CorridorIndex, distance_km


def decode_polyline(encoded, precision=6):
    if not isinstance(encoded, str) or not 0 < len(encoded) <= 2_000_000:
        raise ValueError('Invalid reference shape')
    index = lat = lon = 0
    points = []

    def signed():
        nonlocal index
        value = shift = 0
        while index < len(encoded):
            byte = ord(encoded[index]) - 63
            index += 1
            if not 0 <= byte <= 63 or shift >= 35:
                raise ValueError('Invalid reference shape integer')
            value |= (byte & 31) << shift
            if byte < 32:
                return -(value // 2) - 1 if value & 1 else value // 2
            shift += 5
        raise ValueError('Truncated reference shape')

    while index < len(encoded):
        lat += signed()
        lon += signed()
        point = [lon / 10**precision, lat / 10**precision]
        if not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90:
            raise ValueError('Reference shape outside coordinate bounds')
        points.append(point)
    if len(points) < 2:
        raise ValueError('Reference shape has no segment')
    return points


def arc_geometry(data, arc):
    if not 0 <= arc < len(data['arcFrom']):
        raise ValueError('Invalid source arc')
    point = lambda node: list(data['nodeCoordinates'][node*2:node*2+2])
    first, last = data['arcInteriorOffsets'][arc:arc+2]
    start, end = data['arcByteOffsets'][arc:arc+2]
    values = list(decode_signed32([data['geometryBytes'][start:end]], 2*(last-first)))
    if len(values) != 2*(last-first):
        raise ValueError('Source geometry/cumulative count mismatch')
    points = [point(data['arcFrom'][arc])]
    x, y = [round(value*100000) for value in points[0]]
    for dx, dy in zip(values[::2], values[1::2]):
        x += dx
        y += dy
        points.append([x/100000, y/100000])
    points.append(point(data['arcTo'][arc]))
    cumulative = [0., *data['interiorSourceKm'][first:last], data['arcRoadKm'][arc]]
    if not all(math.isfinite(b) and b >= a for a, b in zip(cumulative, cumulative[1:])):
        raise ValueError('Invalid cumulative source distances')
    return points, cumulative


def source_samples(points, cumulative, step_km=1):
    """Sample simplified spans, weighting by original cumulative source length."""
    if step_km <= 0 or len(points) != len(cumulative):
        raise ValueError('Invalid source sampling input')
    for i, (a, b) in enumerate(zip(points, points[1:])):
        weight = cumulative[i+1] - cumulative[i]
        if weight < 0:
            raise ValueError('Negative source length')
        if not weight:
            continue
        count = max(1, math.ceil(distance_km(a, b) / step_km))
        for j in range(count):
            t = (j+.5)/count
            yield [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t], weight/count


class MultiCorridorIndex(CorridorIndex):
    """Reuse the sealed distance query with explicitly disconnected path parts."""
    def __init__(self, parts, step=.05):
        if step <= 0:
            raise ValueError('Invalid index step')
        self.step = step
        self.segments = [(a, b) for points in parts for a, b in zip(points, points[1:])]
        self.bins = defaultdict(list)
        for i, (a, b) in enumerate(self.segments):
            for x in range(math.floor(min(a[0], b[0])/step), math.floor(max(a[0], b[0])/step)+1):
                for y in range(math.floor(min(a[1], b[1])/step), math.floor(max(a[1], b[1])/step)+1):
                    self.bins[x, y].append(i)


def overlap(samples, index, radii=(1, 3)):
    total = math.fsum(weight for _, weight in samples)
    return {str(radius): (math.fsum(weight for point, weight in samples if index.within(point, radius))/total
                         if total else None) for radius in radii}


def account_path(path, data, base_cells):
    """Verify every captured detailed edge and reconcile all remaining minutes."""
    parts, samples, audits = [], [], []
    costs = defaultdict(float)
    classes = defaultdict(lambda: {'sourceKm': 0., 'minutes': 0., 'edges': 0})
    for edge in path['edges']:
        minutes = edge['minutes']
        if not math.isfinite(minutes) or minutes <= 0:
            raise ValueError('Nonpositive captured path edge')
        if 'arc' in edge:
            arc = edge['arc']
            points, cumulative = arc_geometry(data, arc)
            nodes = [data['arcFrom'][arc], data['arcTo'][arc]]
            captured = [edge['from']-base_cells, edge['target']-base_cells]
            reverse = captured == nodes[::-1]
            if edge['kind'] != 'road' or (captured != nodes and not reverse):
                raise ValueError('Captured source incidence mismatch')
            expected = [points[-1], points[0]] if reverse else [points[0], points[-1]]
            if [edge['fromPoint'], edge['toPoint']] != expected:
                raise ValueError('Captured source coordinate mismatch')
            if minutes != data['arcMinutes'][arc]:
                raise ValueError('Captured source time mismatch')
            if data['arcSpeedKph'][arc] not in (85, 105):
                raise ValueError('Unexpected source speed')
            if minutes + 1e-8 < distance_km(points[0], points[-1])/data['arcSpeedKph'][arc]*60:
                raise ValueError('Captured source chord is undercharged')
            costs['detailedCensusMinutes'] += minutes
            group = classes[str(data['arcSpeedKph'][arc])]
            group['sourceKm'] += data['arcRoadKm'][arc]
            group['minutes'] += minutes
            group['edges'] += 1
            points_in_order = points[::-1] if reverse else points
            parts.append(points_in_order)
            samples.extend(source_samples(points, cumulative))
            geometry = json.dumps([points, cumulative], separators=(',', ':'), allow_nan=False).encode()
            audits.append({'arc': arc, 'reverse': reverse, 'minutes': minutes,
                           'sourceKm': data['arcRoadKm'][arc], 'speedKph': data['arcSpeedKph'][arc],
                           'vertices': len(points), 'geometryAndCumulativeSha256': hashlib.sha256(geometry).hexdigest()})
        else:
            name = {'road': 'coarseBaseRoadMinutes', 'local': 'localMinutes', 'transfer': 'transferMinutes'}[edge['kind']]
            costs[name] += minutes
            chord = distance_km(edge['fromPoint'], edge['toPoint'])
            if edge['kind'] in ('local', 'transfer') and minutes + 1e-8 < chord/25*60:
                raise ValueError('Captured local/transfer chord is undercharged')
            costs[f"{edge['kind']}RepresentativeChordKm"] += chord
    components = path['components']
    costs['unresolvedOriginMinutes'] = components['origin']
    costs['unresolvedDestinationMinutes'] = components['destination']
    for name in ['detailedCensusMinutes', 'coarseBaseRoadMinutes', 'localMinutes', 'transferMinutes']:
        costs[name] += 0.
    if path['direct']:
        # Direct same-arc metadata omits original cumulative positions. Preserve
        # its accounted cost without claiming full detailed-edge geometry.
        if path['edges']:
            raise ValueError('Direct path unexpectedly has graph edges')
        costs['unresolvedDirectRoadMinutes'] = components['road']
    else:
        costs['unresolvedDirectRoadMinutes'] = 0.
        if abs(costs['detailedCensusMinutes']+costs['coarseBaseRoadMinutes']-components['road']) > 1e-8:
            raise ValueError('Captured road component mismatch')
        for name in ['local', 'transfer']:
            if abs(costs[name+'Minutes'] - components[name]) > 1e-8:
                raise ValueError('Captured nonroad component mismatch')
    keys = ['detailedCensusMinutes', 'coarseBaseRoadMinutes', 'localMinutes', 'transferMinutes',
            'unresolvedOriginMinutes', 'unresolvedDestinationMinutes', 'unresolvedDirectRoadMinutes']
    costs['accountedMinutes'] = math.fsum(costs[name] for name in keys)
    if abs(costs['accountedMinutes']-path['pointMinutes']) > 1e-8:
        raise ValueError('Complete captured path accounting mismatch')
    source_km = math.fsum(row['sourceKm'] for row in audits)
    if abs(math.fsum(weight for _, weight in samples)-source_km) > 1e-8:
        raise ValueError('Source-weight sampling lost distance')
    costs['detailedCensusTimeShare'] = costs['detailedCensusMinutes']/path['pointMinutes'] if path['pointMinutes'] else 0.
    costs['detailedCensusSourceKm'] = source_km
    return {'parts': parts, 'samples': samples, 'audits': audits, 'costs': dict(costs), 'classes': dict(classes)}
