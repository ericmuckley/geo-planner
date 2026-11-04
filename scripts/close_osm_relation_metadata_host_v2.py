"""Seal a terminal V2-config relation metadata stage, preserving V1's stop."""
import argparse
import json
from pathlib import Path

import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('controls', 'run'))
    args = parser.parse_args()
    name = f'us-osm-car-relation-metadata-v2-{args.stage}-v1'
    root = Path(__file__).resolve().parents[1]/'data/coarse-quality'/name
    cleanup = json.loads((root/'cleanup.json').read_bytes())
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    key = 'relation-metadata-'+args.stage+'-v2'
    closer.STAGES[key] = (name, key)
    closer.close(key)
