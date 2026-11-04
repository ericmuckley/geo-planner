"""Close one completed census stage; never reruns a producer or reads the country source."""
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
sys.path.insert(0,str(REPO/'scripts'))
from coarse_osm_country_screen_v1 import owned_usage

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,value):
    with p.open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def close(stage):
    root=REPO/('data/coarse-quality/us-osm-topology-'+stage+'-v1');target=HERE/('raw-'+stage+'-v1')
    assert not target.exists();owner=json.loads((root/'owner.json').read_text())
    result=subprocess.run(['docker','inspect',owner['name']],capture_output=True,text=True,timeout=10)
    assert result.returncode!=0 and 'No such' in result.stderr
    summary=json.loads((root/'run-summary.json').read_text());assert summary['exitCode']==0
    cleanup=json.loads((root/'cleanup.json').read_text());assert cleanup['independentInspectAbsent']
    files={};target.mkdir()
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink()
        if path.is_dir():continue
        assert path.is_file();name=str(path.relative_to(root));st=path.stat();pin=sha(path)
        files[name]={'bytes':st.st_size,'sha256':pin,'allocatedBytes':st.st_blocks*512}
        if name!='country-screen.so' and not name.endswith('.bin'):
            assert st.st_size<=2097152;dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as stream:stream.write(path.read_bytes())
    closed={'stage':stage,'root':str(root.relative_to(REPO)),'files':files,'usage':owned_usage(root),'independentWorkerAbsent':True}
    if stage=='controls':
        import struct
        decoded={}
        for name,pin in files.items():
            if not name.endswith('.bin'):continue
            raw=(root/name).read_bytes();fmt='<QQII' if '/refs-' in name else '<Q'
            decoded[name]={'sha256':pin['sha256'],'format':fmt,'rows':list(struct.iter_unpack(fmt,raw))}
        write(HERE/'control-typed-rows-v1.json',decoded)
        closed['tinyDecodedRowsSha256']=sha(HERE/'control-typed-rows-v1.json')
    write(HERE/('closed-'+stage+'-v1.json'),closed)
    print(json.dumps({'stage':stage,'files':len(files),'bytes':sum(p['bytes'] for p in files.values()),'usage':closed['usage']}))

if __name__=='__main__':close(sys.argv[1])
