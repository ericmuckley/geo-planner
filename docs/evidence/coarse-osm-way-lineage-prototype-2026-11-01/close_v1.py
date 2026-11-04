"""Close a completed lineage stage; no producer or country source replay."""
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];sys.path.insert(0,str(REPO/'scripts'))
from coarse_osm_country_screen_v1 import owned_usage

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,value):
    with p.open('x') as f:json.dump(value,f,indent=2);f.write('\n')

stage=sys.argv[1];root=REPO/('data/coarse-quality/us-osm-lineage-'+stage+'-v1');target=HERE/('raw-'+stage+'-v1');assert not target.exists()
owner=json.loads((root/'owner.json').read_bytes());absent=subprocess.run(['docker','inspect',owner['name']],capture_output=True,text=True,timeout=10);assert absent.returncode!=0 and 'No such' in absent.stderr
assert json.loads((root/'run-summary.json').read_bytes())['exitCode']==0 and json.loads((root/'cleanup.json').read_bytes())['independentInspectAbsent']
artifacts=json.loads((root/'artifacts.json').read_bytes());files={};target.mkdir();tiny={}
for path in sorted(root.rglob('*')):
    assert not path.is_symlink()
    if path.is_dir():continue
    name=str(path.relative_to(root));s=path.stat();files[name]={'bytes':s.st_size,'sha256':sha(path),'allocatedBytes':s.st_blocks*512}
    if name in artifacts:
        assert files[name]['bytes']==artifacts[name]['bytes'] and files[name]['sha256']==artifacts[name]['sha256']
        if stage=='controls':tiny[name]=path.read_bytes().hex()
        continue
    assert s.st_size<=2097152;dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as stream:stream.write(path.read_bytes())
closed={'stage':stage,'files':files,'usage':owned_usage(root),'independentWorkerAbsent':True}
if stage=='controls':
    write(HERE/'tiny-artifacts-v1.json',tiny);closed['tinyArtifactsSha256']=sha(HERE/'tiny-artifacts-v1.json')
if stage=='run':
    source=REPO/'data/coarse-quality/us-osm-backbone-run-v1/report.json'
    with (HERE/'baseline-input-report-v1.json').open('xb') as stream:stream.write(source.read_bytes())
    closed['baselineReportSha256']=sha(source)
write(HERE/('closed-'+stage+'-v1.json'),closed)
print(json.dumps({'stage':stage,'files':len(files),'usage':closed['usage']}))
