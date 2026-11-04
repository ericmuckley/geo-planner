"""Seal the terminal host-only profile; never starts a worker or repeats it."""
import hashlib
import json
from pathlib import Path
import shutil

from coarse_osm_full_monitor_v1 import owned_usage
from coarse_osm_bulk_pbf import stat_key


def close():
    repo=Path(__file__).resolve().parents[1];relative='data/coarse-quality/us-osm-car-packed-country-profile-v1'
    root=repo/relative;report=repo/'docs/evidence/coarse-osm-car-capacity-2026-11-01'
    destination=report/'packed-country-profile-closed-v2.json';mirror=report/'packed-country-profile-raw-v2'
    assert not destination.exists() and not mirror.exists()
    result=json.loads((root/'report.json').read_bytes())
    assert result['status']=='host_national_packed_candidate_profile_complete' and not (root/'failure.json').exists()
    roster={};mirror.mkdir()
    for path in sorted(root.iterdir()):
        assert path.is_file() and not path.is_symlink()
        before=stat_key(path);size=path.stat().st_size
        with path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
        assert before==stat_key(path)
        ignored=path.suffix!='.json';roster[path.name]={'bytes':size,'sha256':pin,'ignoredLargeAsset':ignored}
        if not ignored:shutil.copyfile(path,mirror/path.name)
    with destination.open('x') as stream:
        json.dump({'root':relative,'roster':roster,'usage':owned_usage(root),
                   'scope':'Closed completed host functional profile, no Docker worker/independent container-absence claim. Query/retention figures exclude full app/geography/snapping and protected Linux qualification.',
                   'closerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},stream,indent=2);stream.write('\n')
    print(json.dumps({'files':len(roster),'usage':owned_usage(root)}))


if __name__=='__main__':close()
