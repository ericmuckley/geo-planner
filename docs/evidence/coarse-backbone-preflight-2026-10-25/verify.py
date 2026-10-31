"""Read-only record/source/asset binding checks; no source pass, route search or network."""
import hashlib
import json
from pathlib import Path

folder=Path(__file__).resolve().parent
repo=folder.parents[2]
load=lambda p:json.loads(p.read_text())
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1048576):h.update(block)
    return h.hexdigest()
manifest=load(folder/'sha256.json')
assert set(manifest)=={str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name!='sha256.json'}
for name,expected in manifest.items():assert digest(folder/name)==expected,name
checks=load(folder/'checks.json')
for category in ['producerFiles','preservedFiles','assetFiles']:
    for name,expected in checks[category].items():assert digest(repo/name)==expected,name
for name,info in checks['priorSealedEvidence'].items():
    base=repo/'docs/evidence'/name
    assert digest(base/'sha256.json')==info['manifestSha256']
    prior=load(base/'sha256.json');assert len(prior)==info['files']
    for path,expected in prior.items():assert digest(base/path)==expected,(name,path)
print(json.dumps({'recordFiles':len(manifest),'producerFiles':len(checks['producerFiles']),
    'priorSealedRuns':len(checks['priorSealedEvidence']),'allBindingsValid':True,
    'v9RuntimeAndUiUnchanged':True,'bothStorageFailuresPreserved':True,'providerRequests':0},indent=2))
