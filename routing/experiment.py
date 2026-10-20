"""Loopback-only, quota-free road reachability experiment on a qualified graph."""

import argparse
from array import array
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sys
from threading import Lock
import time
import uuid

from anchors import file_hash, load_json
from scoped_load import load_graph
from import_roads import distance_m
from maneuver_graph import source_seeds
from native_support import NativeClient, UINT64_MAX


ROOT = Path(__file__).resolve().parent.parent
DISPLAY_LIMIT = 30000
CELL = 0.01


def artifact(path):
    return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def checked_graph(directory):
    manifest = load_json(directory / "manifest.json")
    for name, expected in manifest["artifacts"].items():
        if artifact(directory / name) != expected: raise ValueError(f"Frozen artifact differs: {name}")
    for name, expected in manifest["scripts"].items():
        if file_hash(directory / "recipe" / name) != expected or file_hash(ROOT / "routing" / name) != expected: raise ValueError(f"Frozen recipe differs: {name}")
    return manifest


class SnapIndex:
    def __init__(self, roads):
        self.roads, self.cells = roads, {}
        for road in range(len(roads)):
            x, y, xx, yy = roads.coordinates[road * 4:road * 4 + 4]
            for a in range(math.floor(min(x, xx) / CELL), math.floor(max(x, xx) / CELL) + 1):
                for b in range(math.floor(min(y, yy) / CELL), math.floor(max(y, yy) / CELL) + 1):
                    self.cells.setdefault((a, b), array("I")).append(road)

    def snap(self, graph, point, cutoff):
        latitude = math.degrees(cutoff / 6371008.8)
        longitude = latitude / math.cos(math.radians(abs(point[1]) + latitude))
        candidates = set()
        for a in range(math.floor((point[0] - longitude) / CELL), math.floor((point[0] + longitude) / CELL) + 1):
            for b in range(math.floor((point[1] - latitude) / CELL), math.floor((point[1] + latitude) / CELL) + 1):
                candidates.update(self.cells.get((a, b), ()))
        scale, best = math.cos(math.radians(point[1])), None
        for index in candidates:
            road = self.roads[index]
            a, b = road["fromPoint"], road["toPoint"]
            dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
            denominator = dx * dx + dy * dy
            fraction = max(0, min(1, ((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) / denominator)) if denominator else 0
            snapped = [a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1])]
            candidate = (distance_m(point, snapped), road["id"], index, snapped)
            if best is None or candidate[:2] < best[:2]: best = candidate
        if best is None or best[0] > cutoff: raise ValueError("No supported road within 100 m; choose a point closer to a road")
        chosen, snapped = self.roads[best[2]], best[3]
        starts = []
        for index in sorted(candidates):
            if self.roads.ways[index] != chosen["way"] or self.roads.segments[index] != self.roads.segments[best[2]]: continue
            road = self.roads[index]
            a, b = road["fromPoint"], road["toPoint"]
            dx, dy = b[0] - a[0], b[1] - a[1]
            fraction = ((snapped[0] - a[0]) * dx + (snapped[1] - a[1]) * dy) / (dx * dx + dy * dy) if dx or dy else 0
            starts.append((index, Fraction(str(round(max(0, min(1, fraction)), 12)))))
        return starts, source_seeds(graph, starts), {"input": point, "snapped": snapped, "distanceMeters": best[0]}


def road_prefixes(graph, labels, budget):
    """Legal transition entry costs, including roads whose heads exceed the budget."""
    count = len(graph.base.roads)
    entries = array("Q", [UINT64_MAX]) * count
    rows = graph.adjacency
    for state, cost in enumerate(labels):
        if cost == UINT64_MAX: continue
        for position in range(rows.offsets[state], rows.offsets[state + 1]):
            target = rows.targets[position]
            road = target if target < count else graph.states.extra[target - count][0]
            entry = cost + rows.costs[position] - graph.base.roads.costs[road]
            if entry < 0: raise ValueError("Negative road-entry cost")
            if entry <= budget and entry < entries[road]: entries[road] = entry
    return entries


def intervals(road, cost, entry, budget, direct):
    result = []
    if entry != UINT64_MAX and entry <= budget:
        end = min(1, (budget - entry) / cost)
        if end > 0: result.append((0, end))
    for source, offset in direct:
        if source != road: continue
        start = float(offset)
        end = min(1, start + budget / cost)
        if end > start: result.append((start, end))
    result.sort()
    if len(result) == 2 and result[1][0] <= result[0][1]:
        return [(result[0][0], max(result[0][1], result[1][1]))]
    return result


def reachable_geometry(graph, labels, starts, budget, limit=DISPLAY_LIMIT):
    entries = road_prefixes(graph, labels, budget)
    roads = graph.base.roads
    direct = dict(starts)
    count = sum(1 for road, entry in enumerate(entries) if (entry != UINT64_MAX and entry < budget) or road in direct)
    stride = max(1, math.ceil(count / max(1, limit - 2 * len(direct))))
    lines, ordinal, bounds = [], 0, [180, 90, -180, -90]
    for road, entry in enumerate(entries):
        if entry == UINT64_MAX and road not in direct: continue
        spans = intervals(road, roads.costs[road], entry, budget, [(road, direct[road])] if road in direct else ())
        if not spans: continue
        include = ordinal % stride == 0 or road in direct
        ordinal += 1
        x, y, xx, yy = roads.coordinates[road * 4:road * 4 + 4]
        for start, end in spans:
            a, b = [x + start * (xx - x), y + start * (yy - y)], [x + end * (xx - x), y + end * (yy - y)]
            for lon, lat in (a, b):
                bounds = [min(bounds[0], lon), min(bounds[1], lat), max(bounds[2], lon), max(bounds[3], lat)]
            if include and len(lines) < limit: lines.append([[round(v, 7) for v in a], [round(v, 7) for v in b]])
    return lines, {"reachableDirectedRoads": ordinal, "displayedSegments": len(lines), "sampleStride": stride, "displayLimit": limit, "reachableBounds": bounds if ordinal else None}


def validate_query(body):
    if not isinstance(body, dict) or set(body) != {"origin", "budgetMinutes"}: raise ValueError("Invalid query fields")
    origin, minutes = body["origin"], body["budgetMinutes"]
    if not isinstance(origin, dict) or set(origin) != {"lat", "lon"}: raise ValueError("Invalid origin")
    if type(minutes) is not int or not 1 <= minutes <= 720: raise ValueError("Budget must be 1–720 whole minutes")
    for key, bound in (("lat", 85), ("lon", 180)):
        if type(origin[key]) not in (int, float) or not math.isfinite(origin[key]) or not -bound <= origin[key] <= bound: raise ValueError("Invalid origin coordinates")
    return [origin["lon"], origin["lat"]], minutes * 60000


def feature(kind, geometry, **properties):
    return {"type": "Feature", "properties": {"kind": kind, **properties}, "geometry": geometry}


class Experiment:
    def __init__(self, graph_run, cuts_run):
        directory = ROOT / "data/compact-pilot" / graph_run
        cuts_directory = ROOT / "data/compact-pilot" / cuts_run
        print("Verifying frozen graph and native evidence…", flush=True)
        self.manifest = checked_graph(directory)
        native = load_json(directory / "native-verification.json")
        cuts = load_json(cuts_directory / "report.json")
        identity = self.manifest["graphIdentity"]
        manifest_hash = file_hash(directory / "manifest.json")
        if native["graphIdentity"] != identity or native["sourceManifestSha256"] != manifest_hash or cuts["graphIdentity"] != identity or cuts["sourceManifestSha256"] != manifest_hash: raise ValueError("Qualification/cut identity differs")
        if file_hash(directory / "native_search") != native["compilation"]["binarySha256"] or file_hash(ROOT / "routing/native_search.cpp") != native["compilation"]["sourceSha256"]: raise ValueError("Native binary/source differs")
        if artifact(cuts_directory / "cut-nodes.json") != cuts["artifacts"]["cut-nodes.json"]: raise ValueError("Cut inventory differs")
        self.cuts = load_json(cuts_directory / "cut-nodes.json")
        print("Loading regional graph…", flush=True)
        self.graph, model = load_graph(directory / "graph.json")
        if self.graph.identity != identity or model != self.manifest["profile"]["model"]: raise ValueError("Reload identity/model differs")
        print("Indexing source snaps…", flush=True)
        self.index = SnapIndex(self.graph.base.roads)
        self.cut_states = {row["node"]: [] for row in self.cuts}
        roads = self.graph.base.roads
        for state in range(len(self.graph.states)):
            road = state if state < len(roads) else self.graph.states.extra[state - len(roads)][0]
            node = roads.heads[road]
            if node in self.cut_states: self.cut_states[node].append(state)
        summary = load_json(directory / "summary.json")
        for origin in summary["origins"]:
            if origin["snap"] is None: continue
            _, seeds, snap = self.index.snap(self.graph, origin["snap"]["input"], 100)
            if [list(seed) for seed in seeds] != origin["seeds"] or snap["snapped"] != origin["snap"]["snapped"]: raise ValueError("Indexed snap differs from qualified source")
        self.client = NativeClient(directory / "native_search", directory / "graph.csr", identity)

    def config(self):
        model = self.manifest["profile"]["model"]
        return {"ready": True, "graphIdentity": self.graph.identity, "bounds": self.manifest["profile"]["bbox"], "maxMinutes": 720,
                "model": " / ".join(model[key] for key in ("id", "restrictionGeometryPolicy") if key in model),
                "sourceDate": "2026-10-14T20:21:12Z", "publicApiCalls": 0}

    def query(self, body):
        started = time.perf_counter()
        point, budget = validate_query(body)
        west, south, east, north = self.manifest["profile"]["bbox"]
        if not west <= point[0] <= east or not south <= point[1] <= north: raise ValueError("Origin is outside the experimental dataset")
        starts, seeds, snap = self.index.snap(self.graph, point, 100)
        snap_ms = (time.perf_counter() - started) * 1000
        native, payload, round_trip = self.client.request(seeds, budget)
        labels = array("Q"); labels.frombytes(payload)
        if sys.byteorder != "little": labels.byteswap()
        before = time.perf_counter()
        lines, display = reachable_geometry(self.graph, labels, starts, budget)
        features = [feature("road", {"type": "MultiLineString", "coordinates": lines}),
                    feature("coverage", {"type": "LineString", "coordinates": [[west, south], [east, south], [east, north], [west, north], [west, south]]}),
                    feature("snap", {"type": "Point", "coordinates": snap["snapped"]}, type="snapped")]
        reached, sides, first = 0, dict.fromkeys(("north", "east", "south", "west"), 0), None
        for row in self.cuts:
            cost = min((labels[state] for state in self.cut_states[row["node"]]), default=UINT64_MAX)
            hit = cost != UINT64_MAX and cost <= budget
            if hit:
                reached += 1
                first = min(first, cost) if first is not None else cost
                for side in row["outsideSides"]: sides[side] += 1
            features.append(feature("cut", {"type": "Point", "coordinates": row["point"]}, node=str(row["node"]), reached=hit,
                                    costMs=cost if hit else None, sides=row["outsideSides"], blockedByModel=row["blockedByModel"]))
        warnings = ["Experimental static driving model; no traffic, border queues or current crossing-eligibility verification.",
                    "Road geometry is sampled for display. Search and boundary counts use the full graph. This is not a filled isochrone.",
                    "Source coverage and all-origin completeness remain unverified beyond this regional dataset."]
        if reached: warnings.insert(0, "INCOMPLETE: reachable roads hit the dataset boundary. Missing roads can change routes and travel times.")
        return {"id": str(uuid.uuid4()), "query": body, "geometry": {"type": "FeatureCollection", "features": features},
                "metadata": {**self.config(), "coverageVerified": False, "truncated": reached > 0, "reachedCutNodes": reached,
                             "auditedCutNodes": len(self.cuts), "cutsBySide": sides, "firstReachedCutMs": first, "settledStates": native["settledStates"],
                             "snap": snap, "display": display, "warnings": warnings,
                             "timings": {"snapMs": snap_ms, "nativeSearchMs": native["searchMs"], "nativeRoundTripMs": round_trip,
                                         "geometryMs": (time.perf_counter() - before) * 1000, "workerTotalMs": (time.perf_counter() - started) * 1000}}}


def serve(experiment, port):
    query_lock = Lock()
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body):
            payload = json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload))); self.send_header("Cache-Control", "no-store"); self.end_headers()
            try: self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError): pass

        def do_GET(self):
            if self.path != "/health": return self.send(404, {"error": "Not found"})
            self.send(200, experiment.config())

        def do_POST(self):
            if self.path != "/query": return self.send(404, {"error": "Not found"})
            if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"} or self.headers.get("Origin"):
                return self.send(403, {"error": "Use the app's local server route"})
            if not query_lock.acquire(blocking=False): return self.send(503, {"error": "Another local query is running; retry shortly"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2048 or self.headers.get("Content-Type") != "application/json": raise ValueError("Invalid request body")
                body = json.loads(self.rfile.read(length))
                self.send(200, experiment.query(body))
            except (ValueError, KeyError, TypeError) as error: self.send(400, {"error": str(error)})
            except Exception:
                self.send(503, {"error": "Local routing worker failed; restart it and check its terminal"})
                raise
            finally: query_lock.release()

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Offline experiment ready on http://127.0.0.1:{port}", flush=True)
        try: server.serve_forever()
        finally: experiment.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-run", default="two-hour-region-v2")
    parser.add_argument("--cuts-run", default="two-hour-region-v2-cuts")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    for name in (args.graph_run, args.cuts_run):
        if not name or any(not (character.isascii() and (character.isalnum() or character in "_-")) for character in name): parser.error("Invalid run name")
    serve(Experiment(args.graph_run, args.cuts_run), args.port)
