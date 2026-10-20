import hashlib, json, math, sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "routing"))
from two_hour_frontier import plan, EARTH_METERS, MAX_SPEED_KPH
folder = Path(__file__).parent / "footprints"
rings = {}
for source in sorted(folder.glob("*.poly")):
    polygons, current = [], None
    for line in source.read_text().splitlines()[1:]:
        fields = line.split()
        if len(fields) == 1 and fields[0] != "END":
            if fields[0].startswith("!"): raise ValueError("Hole handling needs a separate assessment")
            current = []
        elif fields == ["END"] and current is not None:
            polygons.append(current); current = None
        elif len(fields) == 2 and current is not None:
            current.append(tuple(map(float, fields)))
    rings[source.stem] = polygons

def within(point, ring):
    x, y = point; inside = False
    for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax: inside = not inside
    return inside

records = json.loads((root / "data/compact-pilot/experiment-region-v1-cuts/cut-nodes.json").read_text())
samples, missing_before, missing_after = 0, [], []
for record in records:
    costs = [w["costMs"] for w in record["origins"].values() if w["costMs"] is not None and w["costMs"] <= 7200000]
    if not costs: continue
    angle = (7200000 - min(costs)) * MAX_SPEED_KPH / 3600 / EARTH_METERS
    lon, lat = map(math.radians, record["point"])
    for degree in range(360):
        bearing = math.radians(degree)
        a = math.asin(math.sin(lat) * math.cos(angle) + math.cos(lat) * math.sin(angle) * math.cos(bearing))
        b = lon + math.atan2(math.sin(bearing) * math.sin(angle) * math.cos(lat), math.cos(angle) - math.sin(lat) * math.sin(a))
        point = [math.degrees(b), math.degrees(a)]; samples += 1
        covered = {name: any(within(point, ring) for ring in polygons) for name, polygons in rings.items()}
        entry = {"node": record["node"], "point": point, "costMs": min(costs)}
        if not (covered["socal"] or covered["mexico"]): missing_before.append(entry)
        if not any(covered.values()): missing_after.append(entry)
result = {"retrievedOn": "2026-10-19", "footprints": {f.name: {"bytes": f.stat().st_size, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()} for f in folder.glob("*.poly")},
    "sampledCirclePerimeters": samples, "outsideCaliforniaMexicoSamples": len(missing_before), "outsideWithArizonaSamples": len(missing_after),
    "beforeExamples": missing_before[:10], "afterExamples": missing_after[:10],
    "frontier": plan(records, [-118, 31.6, -115.5, 34], [-119.8, 30.8, -114.5, 35.5]),
    "scope": "One-degree bearing samples of each reached cut's maximum remaining-time spherical disk. Current extract footprints; not dated extent proofs, exact containment, land classification, source completeness or a coverage certificate."}
print(json.dumps(result, indent=2))
