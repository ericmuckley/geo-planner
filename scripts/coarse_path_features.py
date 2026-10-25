"""Read-only source/geometry features for the frozen 83-case benchmark."""
from collections import defaultdict
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/evidence/coarse-path-features-2026-10-24/protocol.json"
PROTOCOL_SHA256 = "f1991760d513160c22bbd897487373399e8f1c57a124d453306a68e77fc20e72"


def distance_km(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(b[0]-a[0])/2)**2
    return 12742 * math.asin(min(1, math.sqrt(h)))


def polyline_samples(points, step_km=1):
    """Midpoint quadrature per segment; weights exactly retain polyline length."""
    assert step_km > 0
    for a, b in zip(points, points[1:]):
        length = distance_km(a, b)
        if not length:
            continue
        n = max(1, math.ceil(length/step_km))
        for i in range(n):
            t = (i+.5)/n
            yield [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t], length/n


def segment_distance_km(point, a, b):
    scale = math.cos(math.radians(point[1]))
    dx, dy = (b[0]-a[0])*scale, b[1]-a[1]
    denominator = dx*dx+dy*dy
    t = 0 if not denominator else max(0, min(1, ((point[0]-a[0])*scale*dx+(point[1]-a[1])*dy)/denominator))
    return distance_km(point, [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t])


class CorridorIndex:
    """Short-segment bbox index; final membership checks distance to a segment."""
    def __init__(self, points, step=.05):
        assert step > 0
        self.step = step
        self.segments = list(zip(points, points[1:]))
        self.bins = defaultdict(list)
        for i, (a, b) in enumerate(self.segments):
            for x in range(math.floor(min(a[0], b[0])/step), math.floor(max(a[0], b[0])/step)+1):
                for y in range(math.floor(min(a[1], b[1])/step), math.floor(max(a[1], b[1])/step)+1):
                    self.bins[x, y].append(i)

    def within(self, point, radius_km):
        # Conservative angular bbox at contiguous-US latitudes, before exact check.
        dy = radius_km/110
        dx = dy/math.cos(math.radians(abs(point[1])+dy))
        candidates = set()
        for x in range(math.floor((point[0]-dx)/self.step), math.floor((point[0]+dx)/self.step)+1):
            for y in range(math.floor((point[1]-dy)/self.step), math.floor((point[1]+dy)/self.step)+1):
                candidates.update(self.bins.get((x, y), ()))
        return any(segment_distance_km(point, *self.segments[i]) <= radius_km for i in candidates)


def corridor_fraction(samples, index, radius_km):
    total = sum(weight for _, weight in samples)
    return sum(weight for point, weight in samples if index.within(point, radius_km))/total if total else None


def correlation(rows, key):
    selected = [r for r in rows if r[key] is not None]
    x, y = [r[key] for r in selected], [r["signedMinutes"] for r in selected]
    if len(x) < 2:
        return None
    mx, my = mean(x), mean(y)
    denominator = math.sqrt(sum((v-mx)**2 for v in x)*sum((v-my)**2 for v in y))
    return sum((a-mx)*(b-my) for a, b in zip(x, y))/denominator if denominator else None


def analyze():
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256
    protocol = json.loads(PROTOCOL.read_text())
    for name, expected in protocol["inputs"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
    load = lambda name: json.loads((ROOT/name).read_text())
    benchmark = load("docs/evidence/coarse-benchmark-reference-2026-10-24/comparison.json")
    assert benchmark["completedLiveBenchmark"] and len(benchmark["cases"]) == 83
    artifact = load("src/server/data/coarse-grid-v8.json")
    width, size = artifact["width"], artifact["width"]*artifact["height"]
    regional = load("docs/evidence/coarse-finer-2026-10-23/paths.json")
    frontier = json.loads(gzip.decompress((ROOT/"docs/evidence/coarse-frontier-reference-2026-10-23/paths.json.gz").read_bytes()))
    frontier_extra = load("docs/evidence/coarse-frontier-reference-2026-10-23/diagnostic.json")["samples"]
    nodes = json.loads(gzip.decompress((ROOT/"docs/evidence/coarse-class-calibration-2026-10-23/paths.json.gz").read_bytes()))
    proof_maps = []
    for folder, binding in [("resolution-0025-base-v1", "base-build.json"), ("resolution-0025-road-v1", "road-build.json")]:
        b = load(f"docs/evidence/coarse-finer-2026-10-23/{binding}")
        raw = (ROOT/f"data/coarse-quality/{folder}/links.json.gz").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == b["linkProof"]["sha256"]
        proof_maps.append({r["key"]:r for r in json.loads(gzip.decompress(raw))})
    references = {}
    for folder, prefix in [("coarse-frontier-reference-2026-10-23", "frontier/"), ("coarse-control-reference-2026-10-24", ""), ("coarse-benchmark-reference-2026-10-24", "")]:
        base = ROOT/f"docs/evidence/{folder}/reference"
        for name, expected in json.loads((base/"sha256.json").read_text()).items():
            assert hashlib.sha256((base/name).read_bytes()).hexdigest() == expected
        for i, q in enumerate(json.loads((base/"plan.json").read_text())["queries"]):
            body = json.loads((base/f"{i:02}-response.txt").read_text())
            key = prefix+q["id"]
            assert key not in references
            references[key] = body["features"][0]
    assert len(references) == 83
    rows = []
    for case in benchmark["cases"]:
        group, id_ = case["id"].split("/", 1)
        saved = next(r for r in (frontier if group == "frontier" else regional[group]) if r["id"] == id_)
        edges = saved["path"]
        model_nodes = next(r["nodes"] for r in nodes if r["id"] == case["id"] and r["model"] == "v8")
        reference = references[case["id"]]
        assert reference["properties"]["summary"]["duration"]/60 == case["ors"]["minutes"]
        reference_nodes = reference["geometry"]["coordinates"]
        classes = defaultdict(lambda: {"roadKm":0., "connectorKm":0., "roadMinutes":0., "connectorMinutes":0., "recordedMinutes":0.})
        source_chord = 0.
        nonroad_minutes = 0.
        road_recorded = 0.
        for edge in edges:
            if edge["kind"] != "road":
                nonroad_minutes += edge["minutes"]
                continue
            a, b = (edge["from"], edge["to"]) if group == "frontier" else (edge["cell"], edge["target"])
            layer = a >= size
            assert layer == (b >= size)
            a, b = sorted([a % size, b % size])
            key = a*4+{1:0,width+1:1,width:2,width-1:3}[b-a]
            proof = proof_maps[int(layer)][key]
            assert abs(proof["deciseconds"]/600-edge["minutes"]) < 1e-8
            kind = "census-layer" if layer else proof["kind"]
            speed = proof["speedKph"]
            value = classes[f"{kind}/{speed}"]
            value["roadKm"] += proof["roadKm"]
            value["connectorKm"] += proof["localKm"]
            value["roadMinutes"] += proof["roadKm"]/speed*60
            value["connectorMinutes"] += proof["localKm"]/(speed if kind == "natural-earth" else 25)*60
            value["recordedMinutes"] += edge["minutes"]
            source_chord += distance_km(proof["pointA"], proof["pointB"])
            road_recorded += edge["minutes"]
        source_km = sum(v["roadKm"] for v in classes.values())
        connector_km = sum(v["connectorKm"] for v in classes.values())
        ne = [v for key, v in classes.items() if key.startswith("natural-earth/")]
        ne_km = sum(v["connectorKm"] for v in ne)
        ne_paid = sum(v["connectorMinutes"] for v in ne)
        endpoint_minutes = case["v8Model"]["pointMinutes"]-road_recorded-nonroad_minutes
        assert endpoint_minutes >= -1e-7
        if group == "frontier":
            extra = next(r for r in frontier_extra if r["id"] == id_)
            endpoint_km = extra["originAttachment"]["distanceKm"]+extra["destinationAttachment"]["distanceKm"]
        else:
            endpoint_km = sum(saved[k] for k in ("originAccessRoadKm", "originAccessLocalKm", "destinationAccessRoadKm", "destinationAccessLocalKm"))
        predicted_distance = source_km+connector_km+nonroad_minutes/60*25+endpoint_km
        source_rounding = road_recorded-sum(v["roadMinutes"]+v["connectorMinutes"] for v in classes.values())
        assert source_rounding >= -1e-7
        assert source_rounding <= len(edges)/600+1e-7
        ms = list(polyline_samples(model_nodes, protocol["corridor"]["sampleStepKm"]))
        rs = list(polyline_samples(reference_nodes, protocol["corridor"]["sampleStepKm"]))
        mi, ri = CorridorIndex(model_nodes, protocol["corridor"]["segmentIndexDegrees"]), CorridorIndex(reference_nodes, protocol["corridor"]["segmentIndexDegrees"])
        row = {"id":case["id"], "set":group, "origin":case["origin"], "signedMinutes":case["v8"]["signedMinutes"],
            "v8Minutes":case["v8Model"]["pointMinutes"], "orsMinutes":case["ors"]["minutes"], "orsKm":case["ors"]["distanceKm"],
            "sourceRoadKm":source_km, "internalConnectorKm":connector_km, "sourceArcChordRatio":source_km/source_chord if source_chord else None,
            "neConnectorKm":ne_km, "neConnectorKmPer100RoadKm":100*ne_km/source_km if source_km else None,
            "neConnectorPaidMinutes":ne_paid, "connectorOnlyAdditionalMinutesAt55":ne_km/55*60-ne_paid,
            "connectorOnlyAdditionalMinutesAt25":ne_km/25*60-ne_paid,
            "endpointMinutes":endpoint_minutes, "endpointKm":endpoint_km, "nonroadMinutes":nonroad_minutes, "sourceRoundingMinutes":source_rounding,
            "modeledDistanceRatio":predicted_distance/case["ors"]["distanceKm"],
            "modelAnchorPolylineKm":sum(w for _,w in ms), "orsPolylineKm":sum(w for _,w in rs),
            "majorRoadMinuteShare":sum(v["recordedMinutes"] for k,v in classes.items() if k.endswith("/105"))/road_recorded if road_recorded else 0,
            "classes":dict(classes)}
        for radius in protocol["corridor"]["radiiKm"]:
            row[f"modelWithin{radius}KmOfOrs"] = corridor_fraction(ms, ri, radius)
            row[f"orsWithin{radius}KmOfModel"] = corridor_fraction(rs, mi, radius)
        rows.append(row)
        print(f"Measured {len(rows)}/83: {case['id']}", file=sys.stderr, flush=True)
    keys = ["sourceArcChordRatio", "neConnectorKmPer100RoadKm", "modeledDistanceRatio", "modelWithin1KmOfOrs", "orsWithin1KmOfModel", "modelWithin3KmOfOrs", "orsWithin3KmOfModel"]
    summary = {}
    for label, selected in [("all",rows), ("frontier",[r for r in rows if r["set"]=="frontier"]), ("majorDominated",[r for r in rows if r["majorRoadMinuteShare"]>=.9])]:
        summary[label] = {"cases":len(selected), "correlationWithSignedResidual":{k:correlation(selected,k) for k in keys},
            "cohorts":{name:{"cases":len(group), "medianNeConnectorKmPer100RoadKm":median(r["neConnectorKmPer100RoadKm"] for r in group if r["neConnectorKmPer100RoadKm"] is not None) if group else None,
                "medianModelWithin3KmOfOrs":median(r["modelWithin3KmOfOrs"] for r in group if r["modelWithin3KmOfOrs"] is not None) if group else None}
                for name, group in [("v8Faster",[r for r in selected if r["signedMinutes"] < -5]), ("nearZero",[r for r in selected if abs(r["signedMinutes"])<=5]), ("v8Slower",[r for r in selected if r["signedMinutes"] > 5])]} }
    return {"protocolSha256":hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(), "cases":83, "summary":summary, "rows":rows,
        "scope":"Frozen-path component/curvature/proximity diagnostic only; connectors are model geometry, not known drivable roads. Corridor overlap is approximate proximity, not road identity. Components/reference paths differ, so this is not causal ETA decomposition or a candidate result. No fitted parameters, graph/query search, provider/key/env/DB read, activation or national inference."}


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
