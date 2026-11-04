"""Seal a completed relation metadata stage without repeating its source read."""
import argparse
import json
from pathlib import Path

import close_osm_car_paid_host_v1 as closer

closer.STAGES['relation-metadata-controls']=('us-osm-car-relation-metadata-controls-v1','relation-metadata-controls')
closer.STAGES['relation-metadata-run']=('us-osm-car-relation-metadata-run-v1','relation-metadata-run')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('controls','run'))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]/'data/coarse-quality'/f'us-osm-car-relation-metadata-{args.stage}-v1'
    cleanup=json.loads((root/'cleanup.json').read_bytes())
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    closer.close('relation-metadata-'+args.stage)
