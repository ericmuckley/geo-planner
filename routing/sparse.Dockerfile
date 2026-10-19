FROM geo-planner-valhalla-tools:7fd2228e5
COPY wheels /wheels
COPY lock.json /opt/geo-planner-tools-lock.json
RUN python3 - <<'PY'
import hashlib, json, pathlib, zipfile
lock = json.loads(pathlib.Path('/opt/geo-planner-tools-lock.json').read_text())
for wheel in lock['wheels']:
    path = pathlib.Path('/wheels') / wheel['filename']
    assert path.stat().st_size == wheel['bytes']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == wheel['sha256']
    with zipfile.ZipFile(path) as archive:
        archive.extractall('/opt/geo-planner-tools')
PY
ENV PYTHONPATH=/opt/geo-planner-tools
RUN python3 -c 'import osmium, requests; print(osmium.__file__)'
