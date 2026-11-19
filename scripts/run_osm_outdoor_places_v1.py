"""Run the national outdoor-places inventory with the existing offline reader."""
import json
from pathlib import Path
import subprocess
import uuid


REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / 'data/coarse-quality/us-osm-tools-v3'
IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'


def main():
    source = 'data/coarse-quality/us-osm-input-v3/download/http/001.bin'
    root = REPO / 'data/coarse-quality/us-osm-outdoor-places-us-v1'
    # Allow for the staging copies, the owned worker output and its scratch space.
    if 64_500_000_000 + 11_440_386_048 + 104_857_600 + 3*64*1024**2 >= 72*1024**3:
        raise ValueError('Outdoor inventory does not fit the offline storage allowance')
    root.mkdir()
    worker = 'geo-planner-outdoor-' + uuid.uuid4().hex[:12]
    (root / 'owner.json').write_text(json.dumps({'container': worker, 'source': source}))
    args = [
        'docker', 'run', '--rm', '--init', '--name', worker, '--pull=never',
        '--network=none', '--read-only', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--memory=4g', '--memory-swap=4g',
        '--cpus=2', '--pids-limit=64', '--ulimit', 'core=0:0',
        '--ulimit', 'fsize=67108864:67108864', '--tmpfs', '/tmp:rw,size=64m',
        '--env', 'PYTHONPATH=/tools/site:/code', '--env', 'LD_LIBRARY_PATH=/tools/runtime',
        '--env', 'OSMIUM_MAX_INPUT_QUEUE_SIZE=2', '--env', 'OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2',
        '--mount', f'type=bind,src={RUNTIME}/offline/site,dst=/tools/site,readonly',
        '--mount', f'type=bind,src={RUNTIME}/prepare/runtime,dst=/tools/runtime,readonly',
        '--mount', f'type=bind,src={REPO/source},dst=/input.osm.pbf,readonly',
        '--mount', f'type=bind,src={root},dst=/work',
    ]
    for script in ('extract_osm_outdoor_places_v1.py', 'extract_osm_fuel_us_v1.py', 'extract_osm_fuel_sample.py'):
        args += ['--mount', f'type=bind,src={REPO}/scripts/{script},dst=/code/{script},readonly']
    args += ['--entrypoint', 'python3', IMAGE, '-B', '/code/extract_osm_outdoor_places_v1.py',
             '/input.osm.pbf', '/work']
    try:
        with (root / 'worker.log').open('xb') as log:
            subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=2400)
        report = json.loads((root / 'report.json').read_bytes())
        if report['status'] != 'outdoor_places_inventory_complete' or sum(
            asset['bytes'] for asset in report['assets'].values()
        ) >= 64*1024**2:
            raise ValueError('Invalid completed outdoor-places inventory')
        print(json.dumps(report))
    except BaseException as error:
        (root / 'failure.json').write_text(json.dumps({'error': repr(error)}))
        raise
    finally:
        owned = subprocess.run(['docker', 'ps', '-aq', '--filter', f'name=^/{worker}$'],
                               capture_output=True, text=True, check=True, timeout=15).stdout.strip()
        if owned:
            subprocess.run(['docker', 'rm', '-f', owned], check=True, timeout=15)
        (root / 'cleanup.json').write_text(json.dumps({'ownedContainerRemoved': True}))


if __name__ == '__main__':
    main()
