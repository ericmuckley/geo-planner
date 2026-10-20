"""Fetch small public source catalogs/footprints; never download road PBFs."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import urlopen


BASE = "https://download.geofabrik.de/"
REGIONS = {"socal": "north-america/us/california/socal", "mexico": "north-america/mexico",
           "arizona": "north-america/us/arizona", "norcal": "north-america/us/california/norcal",
           "nevada": "north-america/us/nevada", "utah": "north-america/us/utah",
           "new-mexico": "north-america/us/new-mexico", "colorado": "north-america/us/colorado",
           "us-west": "north-america/us-west"}
PROBES = {"san-francisco-area": [-122.4, 37.8], "las-vegas-area": [-115.14, 36.17],
          "st-george-area": [-113.58, 37.1], "western-new-mexico": [-108.7, 35.5],
          "western-colorado": [-108.5, 38.0], "baja": [-112, 27], "sonora": [-110.9, 29.1],
          "fresno-area": [-119.8, 36.7], "los-angeles-area": [-118.2, 34.1]}


class Listing(HTMLParser):
    def __init__(self, filename):
        super().__init__()
        self.filename, self.result, self.links, self.cells = filename, None, [], []

    def handle_starttag(self, tag, attrs):
        if tag == "tr": self.links, self.cells = [], []
        if tag == "a": self.links.extend(value.rsplit("/", 1)[-1] for key, value in attrs if key == "href")

    def handle_data(self, data): self.cells.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "tr" and self.filename in self.links:
            text = " ".join(filter(None, self.cells))
            self.result = {"listingBytes": int(re.search(r"(\d+)\s*$", text)[1]),
                           "listingModified": re.search(r"\d{4}-\d\d-\d\d\s+\d\d:\d\d", text)[0]}


def polygons(text):
    rings, current, hole = [], None, False
    for line in text.splitlines()[1:]:
        fields = line.split()
        if fields == ["END"]:
            if current is not None:
                if len(current) < 3: raise ValueError("Incomplete polygon ring")
                rings.append((hole, current))
                current = None
        elif len(fields) == 1:
            hole, current = fields[0].startswith("!"), []
        elif len(fields) == 2 and current is not None:
            current.append(tuple(map(float, fields)))
    if current is not None or not rings: raise ValueError("Incomplete footprint")
    return rings


def within(point, rings):
    x, y = point
    def ring_contains(ring):
        inside = False
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                inside = not inside
        return inside
    return any(ring_contains(ring) for hole, ring in rings if not hole) and not any(
        ring_contains(ring) for hole, ring in rings if hole)


def collect(output):
    output.mkdir(parents=True, exist_ok=False)
    def fetch(job):
        name, url = job
        try:
            with urlopen(url, timeout=30) as response:
                data = response.read(2 * 1024**2 + 1)
                if len(data) > 2 * 1024**2: raise ValueError("Small metadata fetch exceeded limit")
                headers = {key: response.headers.get(key) for key in ("Last-Modified", "ETag", "Content-Type")}
            (output / name).write_bytes(data)
            return name, {"url": url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "headers": headers}
        except Exception as error:
            return name, {"url": url, "error": str(error)}
    jobs = [(name + extension, BASE + slug + extension) for name, slug in REGIONS.items() for extension in (".html", ".poly")]
    with ThreadPoolExecutor(max_workers=4) as workers:
        files = dict(workers.map(fetch, jobs))
    sources, footprints = {}, {}
    for name, slug in REGIONS.items():
        filename = name + "-261014.osm.pbf"
        parser = Listing(filename)
        if "error" not in files[name + ".html"]: parser.feed((output / (name + ".html")).read_text())
        sources[name] = {"datedUrl": BASE + slug + "-261014.osm.pbf", "datedFilename": filename,
                         "datedListing": parser.result, "pbfDownloaded": False,
                         "datedHeaderVerifiedByThisCollector": False, "datedChecksumVerifiedByThisCollector": False}
        if "error" not in files[name + ".poly"]:
            footprints[name] = polygons((output / (name + ".poly")).read_text())
    report = {"observedAt": datetime.now(timezone.utc).isoformat(), "files": files, "sources": sources,
              "probes": {name: {"point": point, "insideCurrentFootprints": [key for key, rings in footprints.items() if within(point, rings)]}
                         for name, point in PROBES.items()},
              "scope": "Small official HTML listings and current .poly files only. Dated listing availability/bytes are observations, not verified PBF dates/checksums. Approximate interior geographic probes show source gaps, not road existence, exact containment, minimal acquisition geography, dated extent, reachability or complete coverage. Existing cached PBF verification is recorded by the offline source merge separately.",
              "roadDataDownloadedBytes": 0, "routingProviderCalls": 0,
              "collectorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/coverage-pilot/six-hour-catalog-v1"))
    print(json.dumps(collect(parser.parse_args().output), indent=2))
