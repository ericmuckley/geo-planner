"""Small helpers for bounded regional preparation, attachments and route evidence."""

from fractions import Fraction
import math
from pathlib import Path
import subprocess

from anchors import file_hash, load_json, save_json
from import_roads import DEFAULT_SPEEDS, inside
from maneuver_graph import source_seeds
from reference import snap_source


def check_bounds(bounds, available):
    if len(bounds) != 4 or not bounds[0] < bounds[2] or not bounds[1] < bounds[3]:
        raise ValueError("Invalid regional bounds")
    if not inside(bounds[:2], available) or not inside(bounds[2:], available):
        raise ValueError("Requested region extends beyond cached source bounds")


def cached_extract(cache, source, bounds, image_id):
    preparation = load_json(cache / "preparation.json")
    extraction = load_json(cache / "extract.json")
    expected = {"source": source, "bbox": bounds, "imageId": image_id,
                "strategy": "smart; types=restriction,restriction:motorcar,restriction:motor_vehicle,restriction:vehicle"}
    if extraction["identity"] != expected or preparation["source"] != source or preparation["bbox"] != bounds:
        raise ValueError("Cached extraction identity mismatch")
    for name, prefix in (("roads.osm", "xml"), ("region.osm.pbf", "pbf")):
        path = cache / name
        if path.stat().st_size != preparation[f"{prefix}Bytes"] or file_hash(path) != preparation[f"{prefix}Sha256"]:
            raise ValueError("Cached extraction checksum mismatch")
    return cache / "roads.osm", preparation


def supported_xml(source, output, image_id):
    """Drop non-car highway classes, retaining all restriction relations and their references."""
    identity = {"sourceXmlSha256": file_hash(source), "highways": sorted(DEFAULT_SPEEDS), "imageId": image_id,
                "retain": "all restriction relations and referenced objects, including their original tags"}
    path, record = output / "car-roads.osm", output / "car-filter.json"
    if record.exists():
        previous = load_json(record)
        if previous["identity"] != identity or file_hash(path) != previous["sha256"]:
            raise ValueError("Car XML filter identity/checksum mismatch")
        return path
    command = ["osmium", "tags-filter", str(source), "w/highway=" + ",".join(identity["highways"]),
               "r/type=restriction*", "-f", "osm", "-o", str(path), "--overwrite"]
    subprocess.run(["/usr/bin/time", "-v", "-o", str(output / "car-filter-resources.txt"), *command], check=True)
    save_json(record, {"identity": identity, "command": command, "bytes": path.stat().st_size, "sha256": file_hash(path)})
    return path


def snap_attachments(graph, point, max_distance):
    raw, snap = snap_source(graph.base, point, max_distance)
    starts = []
    for road, _ in raw:
        edge = graph.base.roads[road]
        a, b, point = edge["fromPoint"], edge["toPoint"], snap["snapped"]
        dx, dy = b[0] - a[0], b[1] - a[1]
        fraction = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)
        starts.append((road, Fraction(str(round(max(0, min(1, fraction)), 12)))))
    seeds = source_seeds(graph, starts)
    return starts, seeds, {**snap, "seeds": seeds}


def route_to_interior(graph, labels, seeds, starts, road, fraction):
    """Recover one tight, legal path for evidence, including the partial last road."""
    fraction = Fraction(fraction)
    if not 0 < fraction < 1:
        raise ValueError("Route target must be interior")
    full = graph.base.roads[road]["costMs"]
    best, last = math.inf, None
    for incoming, row in enumerate(graph.adjacency):
        if not math.isfinite(labels[incoming]): continue
        for target, weight in row:
            if graph.states[target]["road"] == road:
                cost = labels[incoming] + weight - full + math.ceil(full * fraction)
                if cost < best: best, last = cost, (incoming, target)
    for source, offset in starts:
        if source == road and Fraction(offset) <= fraction:
            direct = math.ceil(full * (fraction - Fraction(offset)))
            if direct < best:
                best, last = direct, None
    if not math.isfinite(best): return {"costMs": None, "states": [], "roadIds": []}
    if last is None: return {"costMs": best, "states": [], "roadIds": [graph.base.roads[road]["id"]], "directSameRoad": True}
    predecessors = {}
    for source, row in enumerate(graph.adjacency):
        if not math.isfinite(labels[source]): continue
        for target, weight in row:
            if labels[source] + weight == labels[target] and target not in predecessors:
                predecessors[target] = source
    source_costs = {}
    for source, cost in seeds:
        source_costs[source] = min(source_costs.get(source, math.inf), cost)
    state, terminal = last
    path, seen = [state], {state}
    while source_costs.get(state) != labels[state]:
        state = predecessors[state]
        if state in seen: raise ValueError("Tight route contains a cycle")
        seen.add(state)
        path.append(state)
    path.reverse()
    path.append(terminal)
    return {"costMs": best, "states": path,
            "roadIds": [graph.base.roads[graph.states[state]["road"]]["id"] for state in path]}
