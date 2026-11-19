"""Close terminal native timing controls without replaying them."""
import json
from pathlib import Path
import subprocess
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]/'data/coarse-quality/us-osm-tagged-timing-controls-v1'
    cleanup=json.loads((root/'cleanup.json').read_bytes());assert cleanup['removed'] and cleanup['independentInspectAbsent']
    owner=json.loads((root/'owner.json').read_bytes())
    found=subprocess.run(['docker','ps','-aq','--filter','label=geo-planner.stream-owner='+owner['label']],capture_output=True,text=True,check=True,timeout=15)
    assert not found.stdout.strip()
    closer.STAGES['tagged-timing-controls']=('us-osm-tagged-timing-controls-v1','tagged-timing-controls');closer.close('tagged-timing-controls')
