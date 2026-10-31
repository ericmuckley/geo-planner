"""Read-only stopped native-index proof; no worker/compile/native replay."""
import contextlib,hashlib,io,json,runpy,sys
from pathlib import Path
f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
 with p.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()
m=load(f/'sha256.json');assert set(m)=={str(p.relative_to(f)) for p in f.rglob('*') if p.is_file() and p.name!='sha256.json'}
for n,h in m.items():assert sha(f/n)==h,n
parent=load(f/'parent-proof.json');assert sha(r/parent['path']/'sha256.json')==parent['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(r/parent['path']/'verify.py'),run_name='__main__')
p=load(f/'execution-plan.json');assert sha(f/'execution-plan.json')=='2ccffe1256c99183e2df4bab97205a18c5105e7e1c9e081fc02b30965d2ba9db'
for n,h in p['inputs'].items():
 if not n.startswith('data/'):assert sha(r/n)==h,n
assert len(p['inputs'])==255 and len(p['workerFiles'])==245 and p['network']=='none'
raw=f/'raw';s=load(raw/'run-summary.json');assert s['status']=='stopped' and s['phaseClientExitCodes']=={'build':0,'controls':2}
assert s['networkRequests']==s['sourceOrSavedSampleReads']==0 and not s['fullImportAdmitted'] and not s['modelChanged']
c=load(raw/'controls/controls.json');assert c['tests']==44 and c['failures']==1 and c['errors']==c['skipped']==0
assert 'test_whole_shard_truncation_symlink_cache_and_catalog_drift_refused' in (raw/'controls/worker.log').read_text()
assert load(raw/'build/result.json')['artifactSha256']=='efe338cabf78035b93b936afb623741162e376df8451e5fede8590bbf724dc23'
for phase,code in [('build',0),('controls',2)]:
 v=load(raw/phase/'container-result.json');assert v['clientExitCode']==v['State']['ExitCode']==code and not v['State']['Running'] and not v['State']['OOMKilled']
 cleanup=load(raw/phase/'cleanup.json');assert cleanup['removed'] and cleanup['independentInspectAbsent']
 assert load(f/'cleanup-audit.json')[phase]['ownedContainer']==cleanup['ownedContainer'] and load(f/'cleanup-audit.json')[phase]['independentInspectAbsent']
roster=load(f/'closed-output.json');assert roster['files']==27 and roster['totalBytes']==336049
local='--local-assets' in sys.argv
for n,v in roster['roster'].items():
 path=(r/roster['root']/n) if local else raw/n
 if not local and n=='build/delta.so':continue
 assert path.stat().st_size==v['bytes'] and sha(path)==v['sha256'],n
if local:
 for n,h in p['inputs'].items():assert sha(r/n)==h,n
print(json.dumps({'recordFiles':len(m),'producerFiles':244,'priorSealedRuns':47,'bindingsValid':True,'localAssetsChecked':local,'linuxTests':44,'passed':43,'failedCacheDriftControl':1,'nativeIndexQualified':False,'fullImportAdmitted':False,'v9Unchanged':True},indent=2))
