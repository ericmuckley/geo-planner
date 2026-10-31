"""Read-only evidence/source/asset bindings, no full source audit or route search."""
import hashlib
import json
from pathlib import Path

folder=Path(__file__).resolve().parent
repo=folder.parents[2]
load=lambda path:json.loads(path.read_text())
def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1048576):value.update(block)
    return value.hexdigest()
manifest=load(folder/'sha256.json')
assert set(manifest)=={str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name!='sha256.json'}
for name,expected in manifest.items():assert digest(folder/name)==expected,name
checks=load(folder/'checks.json')
for category in ['producerFiles','preservedFiles','assetFiles','nextProbeToolBindings']:
    for name,expected in checks[category].items():assert digest(repo/name)==expected,name
for name,record in checks['priorSealedEvidence'].items():
    base=repo/'docs/evidence'/name
    assert digest(base/'sha256.json')==record['manifestSha256'],name
    previous=load(base/'sha256.json');assert len(previous)==record['files']
    for path,expected in previous.items():assert digest(base/path)==expected,(name,path)
assert checks['sourceGeometryPreservationQualified'] and not checks['inlineFormatSizeQualified']
assert not checks['binaryProbeRun'] and not checks['runtimeChanged']
print(json.dumps({'recordFiles':len(manifest),'producerFiles':len(checks['producerFiles']),
    'priorSealedRuns':len(checks['priorSealedEvidence']),'allBindingsValid':True,
    'sourceGeometryPreservationVerified':True,'inlineSizeFailurePreserved':True,
    'v9AndUiUnchanged':True,'binaryProbeRun':False,'providerRequests':0},indent=2))
