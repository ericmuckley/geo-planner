"""Seal terminal native entry resolution/audit stages without repeating them."""
import argparse
import json
from pathlib import Path

import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('controls', 'run'))
    args = parser.parse_args()
    name = 'us-osm-car-entry-resolution-'+args.operation+'-v1'
    root = Path(__file__).resolve().parents[1]/'data/coarse-quality'/name
    cleanup = json.loads((root/'cleanup.json').read_bytes())
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    key = 'entry-resolution-'+args.operation
    closer.STAGES[key] = (name, key)
    closer.close(key)
