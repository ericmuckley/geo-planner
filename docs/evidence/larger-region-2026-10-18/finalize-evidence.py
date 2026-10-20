from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,re,shutil,subprocess

root=Path.cwd(); evidence=root/'docs/evidence/larger-region-2026-10-18'; data=root/'data/experiment-pilot/larger-region-v1'
def load(path): return json.loads(Path(path).read_text())
def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def record(path): return {'bytes':Path(path).stat().st_size,'sha256':sha(path)}
release=load(root/'data/compact-pilot/experiment-region-v1/release.json')
assert release['qualifiedForLocalExperiment'] and not release['coverageVerified']
initial=load(data/'preserved-sha256.json')
changed=[p for p,h in initial.items() if sha(root/p)!=h]
assert set(changed)=={'routing/experiment.py','routing/experiment.mjs','src/routes/experiment.tsx'},changed
prior=load(root/'docs/evidence/local-experiment-2026-10-18/recipe-sha256.json')
assert sha(root/'src/routeTree.gen.ts')==prior['src/routeTree.gen.ts']['sha256']
commands={'npm test':{'exitCode':0,'tests':20,'passed':20},'npm run test:routing':{'exitCode':0,'tests':189,'passed':180,'existingSkips':9},'npm run check':{'exitCode':0,'existingWarnings':1},'npm run typecheck':{'exitCode':0},'npm run build':{'exitCode':0},'npm run build:vercel':{'exitCode':0}}
assert 'tests 20' in (data/'adapter-tests.log').read_text()
assert 'Ran 189 tests' in (data/'routing-tests-final.log').read_text() and 'OK (skipped=9)' in (data/'routing-tests-final.log').read_text()
assert 'Found 1 warning' in (data/'check-final.log').read_text()
assert 'built in' in (data/'build-app.log').read_text() and 'Generated .vercel/output/nitro.json' in (data/'build-vercel.log').read_text()
raw=[];samples=[]
for name in ('expanded-map-v1','expanded-areas-v1'):
 report=load(root/'data/experiment-pilot'/name/'report.json')
 for sample in report['samples']:
  file=root/'data/experiment-pilot'/name/f"{sample['origin']}-{sample['minutes']}.json"
  response=load(file); assert response['metadata']==sample['metadata'] and response['metadata']['graphIdentity']==release['graphIdentity']
  assert response['metadata']['publicApiCalls']==0 and not response['metadata']['coverageVerified']
  geometry=json.dumps(response['geometry'],sort_keys=True,separators=(',',':')).encode()
  raw.append({'path':str(file.relative_to(root)),**record(file),'geometrySha256':hashlib.sha256(geometry).hexdigest()})
  samples.append(sample)
assert len(samples)==20
browser=load(evidence/'browser-checks.json');assert browser['graphIdentity']==release['graphIdentity'] and browser['applicationConsoleErrors']==0 and browser['invalidBudgetDisabled'] and browser['staleResultCleared']
ignore=['.env.local','data/compact-pilot/experiment-region-v1/graph.json']
ignored=subprocess.check_output(['git','check-ignore',*ignore],text=True).splitlines();assert ignored==ignore
staged=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines();assert not staged
new_files=[str(p.relative_to(root)) for p in sorted((root/'routing').rglob('*')) if p.is_file() and str(p.relative_to(root)) not in initial]
recipe_files=sorted(set(changed+new_files))
recipe={p:record(root/p) for p in recipe_files}
(data/'recipe').mkdir(exist_ok=True)
for name in recipe:
 target=data/'recipe'/name;target.parent.mkdir(exist_ok=True,parents=True)
 if target.exists():assert record(target)==recipe[name]
 else:shutil.copyfile(root/name,target)
(evidence/'recipe-sha256.json').write_text(json.dumps(recipe,indent=2)+'\n')
for name in ('source-provenance.json','control-point-comparison.json','expanded-snaps.json','launcher-smoke.json','service-memory.json','vercel-disabled-final.json','check-final.log','routing-tests-final.log'):
 shutil.copyfile(data/name,evidence/name)
links=0;missing=[]
for page in (root/'docs').rglob('*.md'):
 for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',page.read_text()):
  target=target.strip('<>').split('#')[0]
  if not target or re.match(r'^[a-z]+:',target):continue
  links+=1
  if not (page.parent/target).resolve().exists():missing.append((str(page.relative_to(root)),target))
assert not missing,missing
shutil.copyfile(Path(__file__),evidence/'finalize-evidence.py')
result={'completedAtUtc':datetime.now(timezone.utc).isoformat(),'graphIdentity':release['graphIdentity'],'checks':commands,'graphRelease':record(root/'data/compact-pilot/experiment-region-v1/release.json'),'recordedLiveAppCases':20,'apiBudgetsMinutes':[60,90,120,360,720],'browser':browser,'rawResponses':raw,'preservation':{'initialFilesChecked':len(initial),'changedPreexistingFiles':changed,'frozenImportSearchProducersAndLockfileUnchanged':True,'generatedRouteTreeUnchanged':True,'environmentFileReadByAgent':False,'environmentFileEdited':False,'stagedFiles':staged,'ignoredPaths':ignored},'localDocumentationLinksChecked':links,'diskFreeGiB':shutil.disk_usage(root).free/1024**3,'publicRoutingApiCalls':0,'coverageVerified':False,'limitations':['Every selected two-hour case still reaches a potential data edge.','New-town costs are API/browser smoke checks; their snaps match full scans, but new full fields are not separately qualified.','Static model and border access/waits remain uncertain; sampled roads are not filled contours.','Local mode is disabled on Vercel; no cloud deployment or national/12-hour geographic completeness.'],'evidenceSha256':{p.name:record(p) for p in sorted(evidence.iterdir()) if p.is_file() and p.name!='validation.json'}}
(evidence/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('graphIdentity','recordedLiveAppCases','preservation','localDocumentationLinksChecked','diskFreeGiB')},indent=2))
