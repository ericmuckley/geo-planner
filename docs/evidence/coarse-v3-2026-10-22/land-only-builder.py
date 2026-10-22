"""Add geography-checked local shore connections without changing v2 road costs."""

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src/server/data/coarse-grid-v2.json"
BASE_SHA256 = "76d3216310c8c776eab3385b077a1ff6ab85c1f72f542e9a3ff4c7fee852c063"
DIRECTIONS = [(1, 0), (1, 1), (0, 1), (-1, 1)]
spec = importlib.util.spec_from_file_location("v2", Path(__file__).with_name("build-coarse-grid-v2.py"))
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


class Geography:
    def __init__(self, boundary, lakes, south, step, height):
        self.south, self.step, self.height = south, step, height
        self.country = self.rows(boundary)
        self.lakes = self.rows(lakes)

    def rows(self, polygons):
        rows = [[] for _ in range(self.height)]
        for number, polygon in enumerate(polygons):
            for ring in polygon:
                for a, b in zip(ring, ring[1:]):
                    lo = max(0, math.floor((min(a[1], b[1]) - self.south) / self.step))
                    hi = min(self.height - 1, math.floor((max(a[1], b[1]) - self.south) / self.step))
                    for row in range(lo, hi + 1):
                        rows[row].append((number, tuple(a), tuple(b)))
        return rows

    def on_land(self, point):
        row = math.floor((point[1] - self.south) / self.step)
        return 0 <= row < self.height and v2.contains(point, self.country[row]) and not v2.contains(point, self.lakes[row])

    def country_parts(self, point):
        row = math.floor((point[1] - self.south) / self.step)
        inside = set()
        for number, a, b in self.country[row]:
            if (a[1] > point[1]) != (b[1] > point[1]) and point[0] < a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                inside.symmetric_difference_update([number])
        return inside

    def land_segment(self, a, b):
        if not self.on_land(a) or not self.on_land(b):
            return False
        if not self.country_parts(a).intersection(self.country_parts(b)):
            return False  # Separate islands cannot connect by touching a corner.
        cuts = [0, 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        lo = max(0, math.floor((min(a[1], b[1]) - self.south) / self.step))
        hi = min(self.height - 1, math.floor((max(a[1], b[1]) - self.south) / self.step))
        edges = {edge for row in range(lo, hi + 1) for group in [self.country, self.lakes] for edge in group[row]}
        for _, c, d in edges:
            if max(c[0], d[0]) < min(a[0], b[0]) or min(c[0], d[0]) > max(a[0], b[0]):
                continue
            ex, ey = d[0] - c[0], d[1] - c[1]
            denominator = dx * ey - dy * ex
            if abs(denominator) < 1e-15:
                continue
            cx, cy = c[0] - a[0], c[1] - a[1]
            t, u = (cx * ey - cy * ex) / denominator, (cx * dy - cy * dx) / denominator
            if 0 <= t <= 1 and 0 <= u <= 1:
                cuts.append(t)
        cuts.sort()
        return all(self.on_land([a[0] + dx * (t + u) / 2, a[1] + dy * (t + u) / 2])
                   for t, u in zip(cuts, cuts[1:]) if u - t > 1e-10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="src/server/data/coarse-grid-v3.json")
    args = parser.parse_args()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA256, "Preserve the v2 comparison input"
    data = json.loads(BASE.read_text())
    west, south, east, north = data["bounds"]
    width, height, step = data["width"], data["height"], data["step"]
    land = base64.b64decode(data["land"])
    traversable = bytearray(base64.b64decode(data["traversable"]))
    display = bytearray(base64.b64decode(data["displayLand"]))
    offsets = list(struct.unpack(f"<{width * height * 2}h", base64.b64decode(data["anchorOffsets"])))
    geography = Geography(data["boundary"], data["lakes"], south, step, height)

    def center(cell):
        return [west + (cell % width + .5) * step, south + (cell // width + .5) * step]

    def position(cell):
        p = center(cell)
        return [p[k] + offsets[cell * 2 + k] / 100000 for k in (0, 1)]

    # Boundary samples only select candidate cells. Every retained representative
    # and connection is checked against polygon geometry, including small holes.
    candidates, boundary_points = set(), {}
    for polygon in data["boundary"] + data["lakes"]:
        for ring in polygon:
            for a, b in zip(ring, ring[1:]):
                count = max(1, math.ceil(max(abs(a[0] - b[0]), abs(a[1] - b[1])) / (step / 4)))
                for part in range(count + 1):
                    p = [a[k] + (b[k] - a[k]) * part / count for k in (0, 1)]
                    if not (west <= p[0] < east and south <= p[1] < north):
                        continue
                    x, y = math.floor((p[0] - west) / step), math.floor((p[1] - south) / step)
                    cell = y * width + x
                    boundary_points.setdefault(cell, []).append(p)
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if 0 <= x + dx < width and 0 <= y + dy < height:
                                candidates.add((y + dy) * width + x + dx)

    added = 0
    for cell in sorted(candidates):
        if traversable[cell]:
            continue  # Preserve every existing road anchor and road time.
        c = center(cell)
        points = [[c[0] + dx * step, c[1] + dy * step]
                  for dx in (-.4, -.2, 0, .2, .4) for dy in (-.4, -.2, 0, .2, .4)]
        for p in boundary_points.get(cell, []):
            points.extend([[p[0] + dx * .0001, p[1] + dy * .0001]
                           for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]])
        points = [p for p in points if abs(p[0] - c[0]) < step / 2 and abs(p[1] - c[1]) < step / 2]
        points.sort(key=lambda p: v2.distance_km(c, p))
        for p in points:
            delta = [round((p[k] - c[k]) * 100000) for k in (0, 1)]
            quantized = [c[k] + delta[k] / 100000 for k in (0, 1)]
            if geography.on_land(quantized):
                offsets[cell * 2:cell * 2 + 2] = delta
                traversable[cell] = display[cell] = 1
                added += 1
                break

    shore_links = bytearray(width * height)
    links = 0
    for cell in range(width * height):
        if not traversable[cell]:
            continue
        x, y = cell % width, cell // width
        for direction, (dx, dy) in enumerate(DIRECTIONS):
            if not (0 <= x + dx < width and 0 <= y + dy < height):
                continue
            target = (y + dy) * width + x + dx
            if not traversable[target] or (land[cell] and land[target]):
                continue
            if geography.land_segment(position(cell), position(target)):
                shore_links[cell] |= 1 << direction
                links += 1

    data.update({
        "version": "natural-earth-5.1.2-road-grid-v3",
        "traversable": base64.b64encode(traversable).decode(),
        "displayLand": base64.b64encode(display).decode(),
        "anchorOffsets": base64.b64encode(struct.pack(f"<{len(offsets)}h", *offsets)).decode(),
        "shoreLinks": base64.b64encode(shore_links).decode(),
        "shoreLandCells": added, "shoreLocalLinks": links,
        "shoreModel": "Representatives on retained generalized land in mixed cells; bidirectional 25 km/h shore links only along continuous land segments; v2 road anchors, road times, land mask and speeds unchanged",
        "baseArtifactSha256": BASE_SHA256,
    })
    output = ROOT / args.output
    assert output.name not in ["coarse-grid-v1.json", "coarse-grid-v2.json"], "Preserve comparison inputs"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(json.dumps({"output": str(output.relative_to(ROOT)), "bytes": output.stat().st_size,
                      "shoreLandCells": added, "shoreLocalLinks": links,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
