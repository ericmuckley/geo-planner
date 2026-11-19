"""Seal terminal native entry resolution/audit stages without repeating them."""
import argparse
import json
import subprocess
from pathlib import Path

import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('controls', 'run'))
    args = parser.parse_args()
    name = 'us-osm-conditional-entry-resolution-'+args.operation+'-v1'
    root = Path(__file__).resolve().parents[1]/'data/coarse-quality'/name
    cleanup = json.loads((root/'cleanup.json').read_bytes())
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    owner=json.loads((root/'owner.json').read_bytes())
    absent=subprocess.run(['docker','ps','-aq','--filter','label=geo-planner.stream-owner='+owner['label']],capture_output=True,text=True,check=True,timeout=15)
    assert not absent.stdout.strip(),'Conditional entry worker still present'
    key = 'conditional-entry-resolution-'+args.operation
    closer.STAGES[key] = (name, key)
    closer.close(key)
