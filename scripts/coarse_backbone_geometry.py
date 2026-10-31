"""Protected source geometry and sparse indexes for the offline25m preflight."""
from array import array
from fractions import Fraction
import math

from coarse_backbone_codec import encode_signed32
from coarse_path_features import distance_km

METERS_PER_DEGREE = 111320
SCALE = 100000
GRID_SCALE = 40
WEST, SOUTH, WIDTH, HEIGHT = -5000, 960, 2360, 1040
MISSING = 0xffffffff


def grid_axis(value):
    index = math.floor(value * GRID_SCALE)
    while value < index / GRID_SCALE:
        index -= 1
    while value >= (index + 1) / GRID_SCALE:
        index += 1
    return index


def cell(point):
    return grid_axis(point[0]), grid_axis(point[1])


def cell_id(key):
    x, y = key[0] - WEST, key[1] - SOUTH
    return y * WIDTH + x if 0 <= x < WIDTH and 0 <= y < HEIGHT else None


def midpoint(a, b):
    return [(a[axis] + b[axis]) / 2 for axis in [0, 1]]


def crossings(a, b):
    """No epsilon merges: equal rational parameters identify a true grid corner."""
    events = {}
    for axis in [0, 1]:
        low, high = sorted([a[axis], b[axis]])
        if low == high:
            continue
        for index in range(math.floor(low * GRID_SCALE) - 1, math.ceil(high * GRID_SCALE) + 2):
            line = index / GRID_SCALE
            if low < line < high:
                t = (Fraction(line) - Fraction(a[axis])) / (Fraction(b[axis]) - Fraction(a[axis]))
                events.setdefault(t, {})[axis] = line
    for t, lines in sorted(events.items()):
        point = [float(Fraction(a[k]) + t * (Fraction(b[k]) - Fraction(a[k]))) for k in [0, 1]]
        for axis, line in lines.items():
            point[axis] = line
        yield t, point


def expanded_path(points):
    clean = [points[0]]
    for point in points[1:]:
        if point != clean[-1]:
            clean.append(point)
    assert len(clean) >= 2
    result, inserted, lengths = [list(clean[0])], [False], []
    for a, b in zip(clean, clean[1:]):
        previous_t = Fraction(0)
        full_length = distance_km(a, b)
        events = list(crossings(a, b)) + [(Fraction(1), list(b))]
        for t, point in events:
            measured = distance_km(result[-1], point)
            # A rational crossing can round to the same float position as a nearby
            # vertex. Retain its occurrence and positive original source distance.
            lengths.append(measured if measured else full_length * float(t - previous_t))
            result.append(point)
            inserted.append(t != 1)
            previous_t = t
    owners = [cell(midpoint(a, b)) for a, b in zip(result, result[1:])]
    protected = [0]
    for i in range(1, len(result) - 1):
        if inserted[i] or owners[i-1] != owners[i] or cell(result[i]) != owners[i-1]:
            protected.append(i)
    protected.append(len(result)-1)
    return result, lengths, owners, protected


def distance_squared(point, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    norm = dx*dx + dy*dy
    t = 0 if not norm else max(0, min(1, ((point[0]-a[0])*dx + (point[1]-a[1])*dy)/norm))
    return (point[0]-a[0]-t*dx)**2 + (point[1]-a[1]-t*dy)**2


def simplify(points, first, last, epsilon_meters=23):
    threshold = (epsilon_meters / METERS_PER_DEGREE)**2
    keep = {first, last}
    stack = [(first, last)]
    while stack:
        start, end = stack.pop()
        farthest, maximum = None, threshold
        for i in range(start+1, end):
            distance = distance_squared(points[i], points[start], points[end])
            if distance > maximum:
                farthest, maximum = i, distance
        if farthest is not None:
            keep.add(farthest)
            stack.extend([(start, farthest), (farthest, end)])
    return sorted(keep)


def retained_indices(points, first, last, owner):
    if cell(midpoint(points[first], points[last])) != owner:
        # Preserve an original interior witness when a chord would collapse onto
        # a different half-open grid-cell boundary.
        choices = [i for i in range(first+1, last) if cell(points[i]) == owner]
        assert choices, "Missing source-cell interior witness"
        middle = min(choices, key=lambda i: (abs(i-(first+last)/2), i))
        return simplify(points, first, middle)[:-1] + simplify(points, middle, last)
    return simplify(points, first, last)


def quantize_inside(point, owner):
    return [max(owner[k]*2500, min((owner[k]+1)*2500-1, round(point[k]*SCALE))) for k in [0, 1]]


def roster(points):
    cells = []
    def add(value):
        if not cells or value != cells[-1]:
            cells.append(value)
    add(cell(points[0]))
    for a, b in zip(points, points[1:]):
        add(cell(midpoint(a, b)))
        add(cell(b))
    return cells


class GeometryGraph:
    def __init__(self, original_coordinates):
        self.original_nodes = len(original_coordinates)//2
        self.arrays = {"nodeCoordinates": array('d', original_coordinates),
                       "arcFrom": array('I'), "arcTo": array('I'), "arcRoadKm": array('d'),
                       "arcMinutes": array('d'), "arcSpeedKph": array('B'),
                       "arcByteOffsets": array('I', [0]), "arcInteriorOffsets": array('I', [0]),
                       "interiorSourceKm": array('d'), "geometryBytes": bytearray(),
                       "partArcOffsets": array('I', [0]), "crossingFirstArc": array('I')}
        self.cell_pairs = array('Q')
        self.max_deviation_meters = 0.
        self.max_chord_undercharge_meters = 0.
        self.maximum_parent_length_error = self.maximum_parent_minutes_error = 0.
        self.cell_mismatches = 0
        self.original_vertices = self.expanded_vertices = self.retained_vertices = 0

    def add_parent(self, points, source_from, source_to, road_km, deciseconds, speed):
        full, lengths, owners, protected = expanded_path(points)
        self.original_vertices += len(points)
        self.expanded_vertices += len(full)
        total = math.fsum(lengths)
        assert total > 0 and road_km > 0
        factor = road_km / total
        nodes = [source_from]
        for i in protected[1:-1]:
            nodes.append(len(self.arrays['nodeCoordinates'])//2)
            self.arrays['nodeCoordinates'].extend(full[i])
            self.arrays['crossingFirstArc'].append(MISSING)
        nodes.append(source_to)
        source_cells, result_cells = roster(full), []
        first_arc = len(self.arrays['arcFrom'])
        proof = []
        for first, last, a, b in zip(protected, protected[1:], nodes, nodes[1:]):
            owner = owners[first]
            assert all(value == owner for value in owners[first:last])
            chosen = retained_indices(full, first, last, owner)
            decoded = [full[first]]
            encoded_values = []
            previous = [round(v*SCALE) for v in full[first]]
            running = 0.
            # Keep the complete original cumulative distance at retained interior
            # vertices. Simplified chord lengths never determine travel costs.
            distance_at = {}
            interior = set(chosen[1:-1])
            for j in range(first+1, last+1):
                running += lengths[j-1]
                if j in interior:
                    distance_at[j] = running*factor
            for index in chosen[1:-1]:
                quantized = quantize_inside(full[index], owner)
                encoded_values.extend([quantized[k]-previous[k] for k in [0, 1]])
                previous = quantized
                decoded.append([v/SCALE for v in quantized])
                self.arrays['interiorSourceKm'].append(distance_at[index])
            decoded.append(full[last])
            self.arrays['geometryBytes'].extend(encode_signed32(encoded_values))
            self.arrays['arcByteOffsets'].append(len(self.arrays['geometryBytes']))
            self.arrays['arcInteriorOffsets'].append(len(self.arrays['interiorSourceKm']))
            km = math.fsum(lengths[first:last])*factor
            minutes = deciseconds/600 * (km/road_km)
            assert km > 0 and minutes > 0
            arc = len(self.arrays['arcFrom'])
            for name, value in [('arcFrom',a), ('arcTo',b), ('arcRoadKm',km),
                                ('arcMinutes',minutes), ('arcSpeedKph',speed)]:
                self.arrays[name].append(value)
            if b >= self.original_nodes:
                assert self.arrays['crossingFirstArc'][b-self.original_nodes] == MISSING
                self.arrays['crossingFirstArc'][b-self.original_nodes] = arc
            if a >= self.original_nodes:
                assert self.arrays['crossingFirstArc'][a-self.original_nodes]+1 == arc
            for key in {owner, cell(full[first]), cell(full[last])}:
                identity = cell_id(key)
                assert identity is not None, "Source geometry outside frozen grid"
                self.cell_pairs.append((identity << 32) | arc)
            for offset, (left, right) in enumerate(zip(chosen, chosen[1:])):
                for index in range(left, right+1):
                    error = math.sqrt(distance_squared(full[index], decoded[offset], decoded[offset+1]))*METERS_PER_DEGREE
                    self.max_deviation_meters = max(self.max_deviation_meters, error)
            undercharge = (distance_km(full[first], full[last]) - minutes/60*speed)*1000
            self.max_chord_undercharge_meters = max(self.max_chord_undercharge_meters, undercharge)
            segment_cells = roster(decoded)
            for key in segment_cells:
                if not result_cells or key != result_cells[-1]:
                    result_cells.append(key)
            proof.append({'first':first,'last':last,'kept':chosen})
            self.retained_vertices += len(chosen)
        self.cell_mismatches += source_cells != result_cells
        last_arc = len(self.arrays['arcFrom'])
        self.maximum_parent_length_error = max(self.maximum_parent_length_error,
            abs(math.fsum(self.arrays['arcRoadKm'][first_arc:last_arc])-road_km))
        self.maximum_parent_minutes_error = max(self.maximum_parent_minutes_error,
            abs(math.fsum(self.arrays['arcMinutes'][first_arc:last_arc])-deciseconds/600))
        return {'firstArc':first_arc,'lastArc':last_arc,'protected':protected,'spans':proof,
                'sourceCells':source_cells,'resultCells':result_cells}

    def end_part(self):
        self.arrays['partArcOffsets'].append(len(self.arrays['arcFrom']))

    def finish_indexes(self):
        count = array('I', [0])*self.original_nodes
        for a, b in zip(self.arrays['arcFrom'], self.arrays['arcTo']):
            if a < self.original_nodes: count[a] += 1
            if b < self.original_nodes: count[b] += 1
        offsets = array('I', [0])
        for value in count: offsets.append(offsets[-1]+value)
        arcs = array('I', [0])*offsets[-1]
        cursor = offsets[:-1]
        for arc, (a, b) in enumerate(zip(self.arrays['arcFrom'], self.arrays['arcTo'])):
            for node in [a, b]:
                if node < self.original_nodes:
                    arcs[cursor[node]] = arc
                    cursor[node] += 1
        self.arrays['endpointAdjOffsets'], self.arrays['endpointAdjArcs'] = offsets, arcs
        pairs = array('Q', sorted(self.cell_pairs))
        self.cell_pairs = array('Q')
        identities, offsets, arcs = array('I'), array('I', [0]), array('I')
        previous = None
        for pair in pairs:
            identity, arc = pair >> 32, pair & MISSING
            if identity != previous:
                if previous is not None: offsets.append(len(arcs))
                identities.append(identity)
                previous = identity
            arcs.append(arc)
        offsets.append(len(arcs))
        self.arrays['cellIds'], self.arrays['cellArcOffsets'], self.arrays['cellArcs'] = identities, offsets, arcs
        assert all(value != MISSING for value in self.arrays['crossingFirstArc'])
