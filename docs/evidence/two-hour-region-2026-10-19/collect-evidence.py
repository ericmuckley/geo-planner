"""Collect completed experiment proofs; never copy large graphs or environment files."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'data/experiment-pilot/two-hour-region-v1'
OUT = ROOT / 'docs/evidence/two-hour-region-2026-10-19'
DATA = ROOT / 'data'

def load(path): return json.loads(path.read_text())
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024**2): digest.update(block)
    return digest.hexdigest()
def save(name, data):
    path = OUT / name
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
def copy(source, name):
    destination = OUT / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha(destination) != sha(source): raise ValueError('Preserve evidence: ' + str(destination))
    if not destination.exists(): shutil.copyfile(source, destination)

OUT.mkdir(parents=True, exist_ok=True)
files = {
 'source-report.json':'source-pilot/two-hour-parent-v2/report.json',
 'arizona-header.json':'source-pilot/two-hour-parent-v2/arizonaHeader.log',
 'merged-source-info.json':'source-pilot/two-hour-parent-v2/mergedInfo.log',
 'preparation-report.json':'coverage-pilot/two-hour-region-v2/report.json',
 'prior-source-only-preparation.json':'coverage-pilot/two-hour-region-v1/report.json',
 'boundary-reader-calibration.json':'compact-pilot/experiment-region-v1-cuts-streamed/report.json',
 'policy-calibration.json':'compact-pilot/scoped-current-v1/calibration-report.json',
 'policy-calibration-build-report.json':'compact-pilot/scoped-current-v1/build-report.json',
 'policy-fixtures.json':'compact-pilot/two-hour-region-v2/scoped-fixtures.json',
 'build-report.json':'compact-pilot/two-hour-region-v2/build-report.json',
 'build-manifest.json':'compact-pilot/two-hour-region-v2/build-manifest.json',
 'rebuild-report.json':'compact-pilot/two-hour-region-v2-rebuild/build-report.json',
 'qualification-report.json':'compact-pilot/two-hour-region-v2/qualification-report.json',
 'failed-loader-attempt.json':'compact-pilot/two-hour-region-v2/qualification-v1-failure.json',
 'reference-sinks-identity.json':'compact-pilot/two-hour-region-v2/qualification-identity.json',
 'qualification-v2-identity.json':'compact-pilot/two-hour-region-v2/qualification-v2-identity.json',
 'fresh-sink-bootstrap.json':'compact-pilot/scoped-sinks-bootstrap-v1/qualification-identity.json',
 'manifest.json':'compact-pilot/two-hour-region-v2/manifest.json',
 'native-verification.json':'compact-pilot/two-hour-region-v2/native-verification.json',
 'cut-report.json':'compact-pilot/two-hour-region-v2-cuts/report.json',
 'summary.json':'compact-pilot/two-hour-region-v2/summary.json',
 'release.json':'compact-pilot/two-hour-region-v2/release.json',
 'two-hour-acceptance.json':'compact-pilot/two-hour-region-v2/two-hour-acceptance.json',
 'rejected-build.json':'compact-pilot/two-hour-region-v1/build-report.json',
 'rejected-build-reason.json':'compact-pilot/two-hour-region-v1/rejected.json',
 'app-query-samples.json':'experiment-pilot/two-hour-map-v2/report.json',
 'new-area-query-samples.json':'experiment-pilot/two-hour-areas-v2/report.json',
}
for destination, relative in files.items(): copy(DATA / relative, destination)
for name in ['frontier-assessment.py','frontier-assessment.json','preserved-sha256.json','expanded-snaps.py','expanded-snaps.json','expanded-smoke.mjs','vercel-disabled.json','vercel-check.mjs','service-memory.json','source-repeat.py','source-repeat.json','source-duplicate-way.osm']:
    copy(RUN / name, name)
for source in (RUN / 'footprints').glob('*.poly'): copy(source, 'footprints/' + source.name)
for name in ['prepare.log','prepare-v2.log','source.log','source-v2.log','build.log','cuts-calibration.log','scoped-calibration.log','scoped-build.log','rebuild.log','qualification.log','qualification-v2.log','sinks-bootstrap-existing.log','sinks-bootstrap-fresh.log','native.log','cuts.log','release.log','worker.log','npm-test.log','routing-tests.log','check.log','typecheck.log','build-app.log','build-vercel.log','launcher-smoke.log','launcher-wrong-graph.log','api-verification.log','expanded-api.log']:
    copy(RUN / name, name)
acceptance = load(DATA / 'compact-pilot/two-hour-region-v2/two-hour-acceptance.json')
assert acceptance['selectedTwoHourBoundaryCheckPassed']
manifest = load(DATA / 'compact-pilot/two-hour-region-v2/manifest.json')
for name, expected in manifest['scripts'].items():
    assert sha(ROOT / 'routing' / name) == expected
    assert sha(DATA / 'compact-pilot/two-hour-region-v2/recipe' / name) == expected
preserved = load(RUN / 'preserved-sha256.json')
changed = [name for name, expected in preserved.items() if sha(ROOT / name) != expected]
assert set(changed) == {'routing/experiment.mjs','routing/experiment.py','src/routes/experiment.tsx'}, changed
cut_scripts = load(DATA / 'compact-pilot/two-hour-region-v2-cuts/report.json')['scripts']
names = set('routing/' + name for name in set(manifest['scripts']) | set(cut_scripts)) | set(changed) | {'routing/two_hour_release.py','routing/verify-experiment.mjs','routing/scoped_native.py','routing/native_search.cpp','routing/native-network.sb','routing/scoped_region_verification_v3.py','routing/scoped-region-verify-v3.mjs'} | {str(p.relative_to(ROOT)) for p in (ROOT / 'routing').glob('*test.py')}
save('final-recipe-sha256.json', {name: sha(ROOT / name) for name in sorted(names)})
raw = {}
for directory in ['two-hour-map-v2','two-hour-areas-v2']:
    for path in (DATA / 'experiment-pilot' / directory).glob('*.json'):
        raw[str(path.relative_to(ROOT))] = {'bytes':path.stat().st_size,'sha256':sha(path)}
save('raw-responses-sha256.json', raw)
missing = []; links = 0
for doc in (ROOT / 'docs').rglob('*.md'):
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', doc.read_text()):
        target = target.strip('<>').split('#')[0]
        if not target or re.match(r'^[a-zA-Z]+:', target): continue
        target = unquote(target)
        if not (doc.parent / target).exists() and (doc.parent / target).resolve() not in {OUT / 'validation.json', OUT / 'evidence-sha256.json'}: missing.append((str(doc.relative_to(ROOT)), target))
        links += 1
assert not missing, missing
ignored = subprocess.check_output(['git','check-ignore','.env.local','data/source-pilot/two-hour-parent-v2/region.osm.pbf'],cwd=ROOT,text=True).splitlines()
staged = subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines()
save('validation.json', {'graphIdentity':manifest['graphIdentity'],'selectedTwoHourBoundaryCheckPassed':True,'preservedFileCount':len(preserved),'expectedChangedExistingFiles':changed,'localDocumentLinksChecked':links,'ignoredPaths':ignored,'stagedFilesObserved':staged,'agentStagedFiles':[],'publicRoutingApiCalls':0,'coverageVerified':False,'scope':'Completed local graph/app/browser proof. Every previous producer and generated route remains unchanged; three intentional runtime/UI updates. Routing data and environment files stay ignored. No cloud deployment.'})
copy(Path(__file__), 'collect-evidence.py')
save('evidence-sha256.json', {str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()})
for doc in (ROOT / 'docs').rglob('*.md'):
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', doc.read_text()):
        target = target.strip('<>').split('#')[0]
        if target and not re.match(r'^[a-zA-Z]+:', target): assert (doc.parent / unquote(target)).exists(), (doc, target)
print(json.dumps({'evidence':str(OUT),'files':len(list(OUT.rglob('*'))),'links':links,'expectedChanges':changed}))
