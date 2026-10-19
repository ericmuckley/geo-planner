#!/usr/bin/env bash
set -euo pipefail
cd /data
test -f sources-verified.json || { echo 'Run npm run routing:download first.' >&2; exit 1; }
test ! -e build-complete.json || { echo 'Graph already exists. Use a new data directory for a rebuild; see docs/regional-routing.md.' >&2; exit 1; }

# Verify again inside the build container; the marker alone is not trusted.
python3 - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
m = json.load(open('/data/manifest.json'))
assert subprocess.check_output(['valhalla_service', '--version'], text=True).strip() == m['engineVersion']
for s in m['sources'] + m.get('adminSupplements', []):
    p = Path('sources') / s['file']
    with p.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    assert p.stat().st_size == s['bytes'] and digest == s['sha256'], s['file']
    if s in m['sources']:
        header = json.loads(subprocess.check_output(['osmium', 'fileinfo', '-j', str(p)]))
        assert header['header']['option']['osmosis_replication_timestamp'] == m['osmTimestamp'], s['file']
        Path(s['file'] + '.fileinfo.json').write_text(json.dumps(header, indent=2))
PY

mapfile -t source_files < <(python3 -c "import json; print(*(f'sources/{s[\"file\"]}' for s in json.load(open('manifest.json'))['sources']), sep='\n')")
read -r bbox strategy threads max_minutes < <(python3 -c "import json; m=json.load(open('manifest.json')); print(','.join(map(str,m['bbox'])) if m.get('bbox') else 'global',m['extractStrategy'],m['buildConcurrency'],m.get('maxMinutes',120))")
if [ "${#source_files[@]}" -eq 1 ]; then
  full_input="${source_files[0]}"
else
  osmium merge "${source_files[@]}" -o merged.osm.pbf --overwrite
  full_input=merged.osm.pbf
fi
if [ "$bbox" = global ]; then
  ln -sf "/data/$full_input" region.osm.pbf
else
  osmium extract --bbox="$bbox" --strategy="$strategy" "$full_input" -o region.osm.pbf --overwrite
fi
osmium fileinfo -j region.osm.pbf > region-fileinfo.json
mkdir -p tiles
valhalla_build_config --mjolnir-tile-dir /data/tiles --mjolnir-tile-extract /data/tiles.tar --mjolnir-admin /data/admin.sqlite --mjolnir-timezone /data/timezones.sqlite --mjolnir-concurrency "$threads" --service-limits-isochrone-max-time-contour "$max_minutes" > valhalla.json
python3 - <<'PY'
import json
p = 'valhalla.json'
c = json.load(open(p))
c['mjolnir']['data_processing']['use_admin_db'] = True
c['mjolnir']['data_processing']['apply_country_overrides'] = True
json.dump(c, open(p, 'w'), indent=2)
PY
# Supplements restore complete country/state relations without importing the planet.
FULL_INPUT="$full_input" python3 - <<'PY'
import json, os, subprocess
m = json.load(open('manifest.json'))
def run(*args): subprocess.run(args, check=True)
admin_input = os.environ['FULL_INPUT']
if m.get('adminSupplements'):
    run('osmium', 'getid', '-r', admin_input, *(f'r{x}' for x in m['baseAdminRelations']), '-o', 'base-admins.osm.pbf', '--overwrite')
    files = ['base-admins.osm.pbf']
    for i, s in enumerate(m['adminSupplements']):
        p = f'admin-supplement-{i}.osm.pbf'
        run('osmium', 'sort', f'sources/{s["file"]}', '-o', p, '--overwrite')
        run('osmium', 'check-refs', '-r', p)
        files.append(p)
    run('osmium', 'merge', '-H', *files, '-o', 'admins.osh.pbf', '--overwrite')
    run('osmium', 'time-filter', 'admins.osh.pbf', '-o', 'admins.osm.pbf', '--overwrite')
    run('osmium', 'check-refs', '-r', 'admins.osm.pbf')
    admin_input = 'admins.osm.pbf'
run('valhalla_build_admins', '-c', 'valhalla.json', admin_input)
PY
valhalla_build_tiles -c valhalla.json -j "$threads" region.osm.pbf
valhalla_build_extract -c valhalla.json -v
python3 - <<'PY'
import datetime, hashlib, json, sqlite3
from pathlib import Path
m = json.load(open('/data/manifest.json'))
def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
admins = sqlite3.connect('admin.sqlite').execute('SELECT admin_level, iso_code, name FROM admins WHERE admin_level IN (2,4)').fetchall()
codes = {row[1] for row in admins}
assert set(m.get('requiredAdmins', [])).issubset(codes), f'Missing required admins: {set(m.get("requiredAdmins", [])) - codes}'
out = {'manifest': m, 'completedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'admins': admins,
       'artifacts': {p: {'bytes': Path(p).stat().st_size, 'sha256': sha(p)} for p in ['region.osm.pbf', 'valhalla.json', 'admin.sqlite', 'tiles.tar']}}
Path('app.env').write_text(f"VALHALLA_URL=http://127.0.0.1:8002\nVALHALLA_MAX_MINUTES={m.get('maxMinutes',120)}\nVALHALLA_ENGINE_VERSION={m['engineVersion']}\nVALHALLA_GRAPH_VERSION={m['id']}\nVALHALLA_COVERAGE={m['coverage']}\n")
if bounds := m.get('bbox') or m.get('sourceBounds'):
    with open('app.env', 'a') as f: f.write(f'VALHALLA_COVERAGE_BOUNDS={json.dumps(bounds, separators=(",", ":"))}\n')
json.dump(out, open('build-complete.json', 'w'), indent=2)
PY
