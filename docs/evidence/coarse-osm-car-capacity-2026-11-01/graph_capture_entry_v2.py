"""Frozen captured constructor entry; no country source is accessible."""
import json
from pathlib import Path
import time
from coarse_osm_car_cost_capture_v2 import run


def audit():
    plan=json.loads(Path('/inputs/recipe.json').read_bytes());began=time.monotonic();last=began
    def check():
        nonlocal last
        now=time.monotonic()
        if now-last>=15:
            print(json.dumps({'capturedQualificationSeconds':now-began}),flush=True);last=now
    return run(Path('/repo'),Path('/work'),('/artifacts/car-cost-graph.so',plan['artifactSha256']),check)
