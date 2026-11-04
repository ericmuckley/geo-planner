"""Close one terminal entry-graph stage; never repeat the graph producer."""
import argparse
import json
from pathlib import Path
import subprocess

import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('controls', 'run'))
    operation = parser.parse_args().operation
    name = 'us-osm-car-entry-attributes-'+operation+'-v1'
    root = Path(__file__).resolve().parents[1]/'data/coarse-quality'/name
    cleanup = json.loads((root/'cleanup.json').read_bytes())
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    owner = json.loads((root/'owner.json').read_bytes())
    found = subprocess.run(['docker', 'ps', '-aq', '--filter', 'label=geo-planner.stream-owner='+owner['label']], capture_output=True, text=True, check=True, timeout=15)
    assert not found.stdout.strip(), 'Entry attributes owned container remains'
    key = 'entry-attributes-'+operation
    closer.STAGES[key] = (name, key)
    closer.close(key)
