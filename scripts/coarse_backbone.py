"""Pure helpers for the offline Census connectivity/footprint preflight."""
from array import array
import math

from coarse_path_features import distance_km


class Components:
    def __init__(self, count):
        self.parent = array("I", range(count))
        self.rank = bytearray(count)

    def find(self, node):
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def join(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b:
            return
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1


def sections(points, nodes):
    """Split only at exact source endpoints; coordinates are never rounded to join."""
    assert len(points) >= 2
    assert tuple(points[0]) in nodes and tuple(points[-1]) in nodes
    start = 0
    for end in range(1, len(points)):
        if tuple(points[end]) in nodes:
            yield start, end, nodes[tuple(points[start])], nodes[tuple(points[end])]
            start = end
    assert start == len(points) - 1


def quantized_deltas(points, scale=100000):
    previous = (0, 0)
    for point in points:
        current = tuple(round(value * scale) for value in point)
        yield current[0] - previous[0], current[1] - previous[1]
        previous = current


def component_summary(components, starts, ends, lengths):
    groups = {}
    for node in range(len(components.parent)):
        root = components.find(node)
        groups.setdefault(root, {"nodes": 0, "arcs": 0, "roadKm": 0.})["nodes"] += 1
    for a, b, length in zip(starts, ends, lengths):
        root = components.find(a)
        assert root == components.find(b)
        groups[root]["arcs"] += 1
        groups[root]["roadKm"] += length
    ordered = sorted(groups.items(), key=lambda item: (-item[1]["roadKm"], item[0]))
    total = sum(lengths)
    return {"components": len(groups), "roadKm": total,
            "largestRoadLengthFraction": ordered[0][1]["roadKm"] / total if total else 0,
            "top10": [{"root": root, **record} for root, record in ordered[:10]]}


class VertexProbes:
    """Nearest source vertex within a fixed radius, not road snapping/access."""
    def __init__(self, coordinates, radius_km=5, step=.1):
        self.coordinates = coordinates
        self.radius = radius_km
        self.step = step
        self.bins = {}
        self.best = [None] * len(coordinates)
        for i, (lon, lat) in enumerate(coordinates):
            dy = radius_km / 110
            dx = dy / math.cos(math.radians(abs(lat) + dy))
            for x in range(math.floor((lon-dx)/step), math.floor((lon+dx)/step)+1):
                for y in range(math.floor((lat-dy)/step), math.floor((lat+dy)/step)+1):
                    self.bins.setdefault((x, y), []).append(i)

    def consider(self, point, node):
        key = math.floor(point[0]/self.step), math.floor(point[1]/self.step)
        for i in self.bins.get(key, ()):
            distance = distance_km(point, self.coordinates[i])
            if distance <= self.radius and (self.best[i] is None or distance < self.best[i]["distanceKm"]):
                self.best[i] = {"distanceKm": distance, "point": list(point), "node": node}
