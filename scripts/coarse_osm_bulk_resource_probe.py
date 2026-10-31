"""Network-free low-memory guard and newly implemented SQLite cap probe."""
import json
from pathlib import Path
import sqlite3
import tempfile

from coarse_osm_resource_probe import probe
from coarse_osm_bulk import Coordinates
from coarse_timing_input import require


def resource_probe():
    result = probe()
    with tempfile.TemporaryDirectory() as name:
        caps = {'sqlitePageBytes': 4096, 'sqliteMaxPagesEach': 4, 'sqliteCacheBytesEach': 8192, 'sqliteIndexBytesEach': 16384}
        index = Coordinates(Path(name) / 'bounded.sqlite', caps); full = False
        try:
            for i in range(10000): index.add({'id': i + 1, 'lon': .12345678, 'lat': .87654321})
        except sqlite3.DatabaseError: full = True
        finally: index.close()
        require(full and (Path(name) / 'bounded.sqlite').stat().st_size <= 16384, 'SQLite page cap not enforced')
    result.update(sqlitePageCapStoppedWrites=True, sqliteCapBytes=16384,
        scope='New bounded SQLite plus reused safe1GiB OOM/watchdog/timer guards, network disabled. No actual4GiB/native-decoder/data/latency/peak-memory qualification.')
    return result


if __name__ == '__main__': print(json.dumps(resource_probe(), indent=2))
