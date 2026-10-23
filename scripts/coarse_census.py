"""Hash-checked offline Census primary/secondary road adapter (no runtime use)."""

import hashlib
import io
import json
import sys
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEEDS = {"S1100": 105, "S1200": 80}  # Global assumptions, not calibrated ETAs.


def checked_file(lock):
    path = ROOT / lock["path"]
    assert path.stat().st_size == lock["bytes"], f"Unexpected size: {path}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == lock["sha256"], f"Unexpected hash: {path}"
    return path


def load_tool(lock_path):
    lock = json.loads((ROOT / lock_path).read_text())
    assert lock["name"] == "pyshp" and lock["version"] == "2.3.1"
    wheel = checked_file(lock)
    sys.path.insert(0, str(wheel))
    import shapefile
    assert Path(shapefile.__file__).as_posix().startswith(wheel.as_posix() + "/")
    return shapefile, lock


def shape_parts(shape):
    breaks = list(shape.parts) + [len(shape.points)]
    return [shape.points[start:stop] for start, stop in zip(breaks, breaks[1:])]


def part_key(part):
    """Exact, direction-independent geometry/class identity across partitions."""
    points = tuple(tuple(point) for point in part["points"])
    points = min(points, tuple(reversed(points)))
    raw = struct.pack(f"<{len(points) * 2}d", *(v for point in points for v in point))
    return hashlib.sha256(part["class"].encode() + raw).digest()


def road_parts(source, shapefile):
    """Yield each multipart section separately; never bridge distinct parts."""
    with zipfile.ZipFile(checked_file(source)) as archive:
        shp_name, = [name for name in archive.namelist() if name.endswith(".shp")]
        stem = shp_name[:-4]
        projection = archive.read(stem + ".prj").decode()
        assert 'GEOGCS["GCS_North_American_1983"' in projection, "Expected geographic NAD83"
        with shapefile.Reader(shp=io.BytesIO(archive.read(shp_name)),
                              dbf=io.BytesIO(archive.read(stem + ".dbf"))) as reader:
            count = 0
            for feature in reader.iterShapeRecords():
                props, shape = feature.record.as_dict(), feature.shape
                assert shape.shapeType == shapefile.POLYLINE
                assert props["MTFCC"] in SPEEDS, "Unexpected primary/secondary road class"
                count += 1
                for part, points in enumerate(shape_parts(shape)):
                    yield {"id": props["LINEARID"], "record": count - 1, "class": props["MTFCC"], "part": part,
                           "points": points}
            assert count == len(reader)
