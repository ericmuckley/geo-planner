"""Run one sample or national fuel inventory with the existing offline reader."""
import argparse
import json
from pathlib import Path
import subprocess
import uuid


REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / 'data/coarse-quality/us-osm-tools-v3'
ASSETS = {
    'sample': ('data/reference-pilot/downtown-static-v1/region.osm.pbf',
               'c1830a4f833e1bfb4b8420b1ecf1127a0405e6df14267ca5aeab647e9a8cae89'),
    'us': ('data/coarse-quality/us-osm-input-v3/download/http/001.bin',
           '1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'),
}
IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scope', choices=ASSETS)
    scope = parser.parse_args().scope
    source, pin = ASSETS[scope]
    root = REPO / f'data/coarse-quality/us-osm-fuel-{scope}-v1'
    # Existing offline storage ceiling, including both new fuel roots.
    if 64_500_000_000 + 11_433_152_512 + 104_857_600 + 3*64*1024**2 >= 72*1024**3:
        raise ValueError('Fuel inventory does not fit the offline storage allowance')
    root.mkdir()
    worker = 'geo-planner-fuel-' + uuid.uuid4().hex[:12]
    (root / 'owner.json').write_text(json.dumps({'container': worker, 'source': source, 'sha256': pin}))
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
    for script in ('extract_osm_fuel_us_v1.py', 'extract_osm_fuel_sample.py'):
        args += ['--mount', f'type=bind,src={REPO}/scripts/{script},dst=/code/{script},readonly']
    args += ['--entrypoint', 'python3', IMAGE, '-B', '/code/extract_osm_fuel_us_v1.py',
             '/input.osm.pbf', '/work', pin]
    if scope == 'sample':
        args.append('--sample')
    try:
        with (root / 'worker.log').open('xb') as log:
            subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=2400)
        report = json.loads((root / 'report.json').read_bytes())
        if report['status'] != 'fuel_inventory_complete' or report['dataBytes'] >= 64*1024**2:
            raise ValueError('Invalid completed fuel inventory')
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
