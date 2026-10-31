"""One bounded PBF-tail diagnostic after a failed relation-member guard.

Captures the relation immediately after a recorded accepted ID. This is diagnosis,
not a source-wide metadata/EOF or extraction admission.
"""
import argparse
import datetime
import hashlib
import itertools
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import uuid
import zlib

from coarse_osm_bulk_pbf import fields, singular, stat_key
from coarse_osm_records import canonical
from coarse_timing_input import require,start_watchdog

IMAGE='sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
OUTPUT='data/coarse-quality/us-osm-member-diagnostic-v2'
MIB=1024**2


def unpack(raw):
    # Reuse the frozen checked protobuf integer decoder with a synthetic field tag.
    values=[];position=0
    while position<len(raw):
        value=0
        for shift in range(0,70,7):
            require(position<len(raw),'Diagnostic truncated packed value')
            byte=raw[position];position+=1
            require(shift<63 or byte<=1,'Diagnostic packed overflow')
            value|=(byte&127)<<shift
            if byte<128:
                require(shift==0 or byte!=0,'Diagnostic noncanonical packed value');break
        else:raise ValueError('Diagnostic packed length')
        values.append(value)
        require(len(values)<=262144,'Diagnostic packed count cap')
    return values


def decode_relation(raw,strings,granularity,*,materialize=True):
    entries=list(fields(raw));buckets={}
    for key,wire,value in entries:buckets.setdefault(key,[]).append((wire,value))
    def scalar(key,default=0):
        items=buckets.get(key,[]);require(len(items)<=1 and (not items or items[0][0]==0),'Diagnostic scalar shape')
        return items[0][1] if items else default
    def packed(key):
        result=[]
        for wire,value in buckets.get(key,[]):
            require(wire in (0,2),'Diagnostic packed wire');result.extend([value] if wire==0 else unpack(value))
        require(len(result)<=262144,'Diagnostic relation list bound');return result
    def text(index):
        require(0<=index<len(strings),'Diagnostic string-table index');return strings[index].decode('utf-8')
    keys,values=packed(2),packed(3);roles,refs,types=packed(8),packed(9),packed(10)
    require(len(keys)==len(values) and len(roles)==len(refs)==len(types),'Diagnostic relation array sizes')
    info=buckets.get(4,[]);require(len(info)==1 and info[0][0]==2,'Diagnostic relation info')
    meta=singular(info[0][1]);timestamp=meta.get(2,(0,0))[1]*granularity
    require(timestamp%1000==0,'Diagnostic timestamp precision')
    stamp=datetime.datetime.fromtimestamp(timestamp//1000,datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    pairs=[(text(k),text(v)) for k,v in zip(keys,values)]
    require(len(dict(pairs))==len(pairs),'Diagnostic duplicate tags')
    members=[];identity=0;invalid=0;member_json_bytes=0
    charge=256+sum(len(k.encode())+len(v.encode())+64 for k,v in pairs)
    for role,delta,kind in zip(roles,refs,types):
        identity+=(delta>>1)^-(delta&1)
        role=text(role);charge+=128+len(role.encode())
        valid=kind<3 and 0<identity<2**63;invalid+=int(not valid)
        kind_name=('node','way','relation')[kind] if kind<3 else 'invalid-'+str(kind)
        member_json_bytes+=24+len(str(identity))+len(canonical(role))+len(canonical(kind_name))
        if materialize:members.append({'type':kind_name,'ref':identity,'role':role})
    row={'type':'relation','id':scalar(1),'version':meta.get(1,(0,0))[1],'timestamp':stamp,
         'visible':bool(meta.get(6,(0,1))[1]),'tags':dict(pairs),'members':members}
    canonical_bytes=len(canonical(row)) if materialize else len(canonical(row))+member_json_bytes+max(0,len(refs)-1)
    require(canonical_bytes<=16*MIB,'Diagnostic retained object bound')
    return row,{'members':len(refs),'invalidMemberIdentitiesOrTypes':invalid,'oldIncrementalCopyCharge':charge,
                'canonicalBytes':canonical_bytes,'oldCopyLimit':MIB,'canonicalLimit':MIB}


def payload(blob):
    data=singular(blob)
    require(set(data)<={1,2,3} and ((1 in data)!=(3 in data)),'Diagnostic blob fields')
    if 1 in data:raw=data[1][1]
    else:
        require(data[2][0]==0 and 0<data[2][1]<32*MIB and data[3][0]==2,'Diagnostic blob size')
        decoder=zlib.decompressobj();raw=decoder.decompress(data[3][1],data[2][1]+1)
        require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(raw)==data[2][1],'Diagnostic decompression')
    require(len(raw)<32*MIB,'Diagnostic raw blob bound');return raw


def worker(plan,root):
    root=Path(root);watchdog=start_watchdog(600);began=time.monotonic()
    def check():require(time.monotonic()-began<600,'Diagnostic worker deadline')
    def save(name,value):
        data=canonical(value)+b'\n';require(len(data)<=16*MIB,'Diagnostic output cap')
        with (root/name).open('xb') as stream:stream.write(data)
    def guard_source():
        before=stat_key('/source.pbf');digest=hashlib.sha256();md5=hashlib.md5();count=0
        with Path('/source.pbf').open('rb') as stream:
            while body:=stream.read(8*MIB):check();count+=len(body);require(count<=plan['source']['bytes'],'Diagnostic source cap');digest.update(body);md5.update(body)
        require(count==plan['source']['bytes'] and digest.hexdigest()==plan['source']['sha256'] and md5.hexdigest()==plan['source']['md5'] and stat_key('/source.pbf')==before,'Diagnostic source identity')
        return before
    try:
        require(int(Path('/sys/fs/cgroup/memory.max').read_text())==4*1024**3 and int(Path('/sys/fs/cgroup/memory.swap.max').read_text())==0,'Diagnostic memory/swap')
        for name,pin in plan['workerFiles'].items():require(hashlib.sha256(Path(name).read_bytes()).hexdigest()==pin,'Diagnostic code binding')
        before=guard_source();target=None;found=False;decoded=read=blocks=relations=0;max_copy=max_canonical=0;largest_copy=largest_canonical=None;invalid_total=0
        cutoff=plan['source']['bytes']-256*MIB
        with Path('/source.pbf').open('rb') as stream:
            while prefix:=stream.read(4):
                check();blocks+=1;require(blocks<=500000 and len(prefix)==4,'Diagnostic frame count/length')
                length=struct.unpack('!I',prefix)[0];require(0<length<65536,'Diagnostic BlobHeader size')
                header=singular(stream.read(length));kind=header[1][1];size=header[3][1]
                require(kind in (b'OSMHeader',b'OSMData') and 0<size<=32*MIB+65536,'Diagnostic frame bounds')
                offset=stream.tell()
                if kind==b'OSMHeader' or offset+size<cutoff:stream.seek(size,1);continue
                read+=size;require(read<=320*MIB,'Diagnostic compressed tail cap')
                data=payload(stream.read(size));decoded+=len(data);require(decoded<=4*1024**3,'Diagnostic decoded tail cap')
                primitive=list(fields(data));strings=[];granularity=1000
                for key,wire,value in primitive:
                    if key==1:strings=[v for k,w,v in fields(value) if k==1 and w==2]
                    if key==18:granularity=value
                require(strings and 0<granularity<2**31 and granularity%1000==0,'Diagnostic primitive settings')
                for key,wire,group in primitive:
                    if key!=2:continue
                    for tag,wire,record in fields(group):
                        if tag!=4:continue
                        identity=next((v for k,w,v in fields(record) if k==1 and w==0),None)
                        relations+=1;require(relations<=2000000,'Diagnostic relation count cap')
                        ignored,stats=decode_relation(record,strings,granularity,materialize=False)
                        invalid_total+=stats['invalidMemberIdentitiesOrTypes']
                        if stats['oldIncrementalCopyCharge']>max_copy:
                            largest_copy,_=decode_relation(record,strings,granularity);max_copy=stats['oldIncrementalCopyCharge']
                        if stats['canonicalBytes']>max_canonical:
                            largest_canonical,_=decode_relation(record,strings,granularity);max_canonical=stats['canonicalBytes']
                        if found and target is None:
                            require(relations==plan['failedRelationOrdinal'],'Diagnostic exact failure ordinal')
                            target,observed=decode_relation(record,strings,granularity)
                            require(observed==stats and target['id']>plan['afterRelationId'],'Diagnostic exact canonical size/next ordering')
                            save('relation.json',target);save('object-stats.json',stats)
                        if identity==plan['afterRelationId']:found=True
        require(target is not None and relations==plan['relationCount'],'Diagnostic complete relation section/target not found in fixed tail')
        save('largest-copy-relation.json',largest_copy);save('largest-canonical-relation.json',largest_canonical)
        save('relation-size-census.json',{'relationCount':relations,'maxOldIncrementalCopyCharge':max_copy,'maxCanonicalBytes':max_canonical,'invalidMemberIdentitiesOrTypes':invalid_total,'scope':'Size/identity census of complete relation section in fixed tail; not a native full-source validation/semantic/EOF qualification'})
        require(stat_key('/source.pbf')==before,'Diagnostic source stat drift');guard_source()
        save('result.json',{'status':'captured_exact_next_relation','relationId':target['id'],'afterRelationId':plan['afterRelationId'],
             'compressedTailBytes':read,'decodedTailBytes':decoded,'headersVisited':blocks,'seconds':time.monotonic()-began,
             'normalWholeSourceEof':False,'qualifiedForExtraction':False})
        return 0
    except BaseException as error:
        save('failure.json',{'status':'stopped','error':str(error),'normalWholeSourceEof':False});return 2
    finally:
        if watchdog.poll() is None:watchdog.terminate()
        watchdog.wait(timeout=5)


def driver(recipe,pin):
    from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
    path=Path(recipe).resolve();require(hashlib.sha256(path.read_bytes()).hexdigest()==pin,'Diagnostic recipe hash')
    plan=json.loads(path.read_text());repo=Path(__file__).resolve().parents[1];root=repo/OUTPUT
    require(plan['output']==OUTPUT and not root.exists(),'Diagnostic new owned output')
    root.mkdir();(root/'execution-plan.json').write_bytes(path.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-member-diag-'+owner[:12];identity=child=None;began=time.monotonic();success=False
    def save(name,value):(root/name).write_text(json.dumps(value,indent=2)+'\n')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
    save('owner.json',{'name':name,'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'})
    try:
        for input_path,expected in plan['inputs'].items():require(hashlib.sha256((repo/input_path).read_bytes()).hexdigest()==expected,'Diagnostic input hash')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--tmpfs','/tmp:rw,size=256m']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={repo/plan["source"]["path"]},dst=/source.pbf,readonly','--mount',f'type=bind,src={root},dst=/work',
               '--mount',f'type=bind,src={path},dst=/inputs/plan.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/diagnose_osm_member_v2.py','/inputs/plan.json',pin,'--worker']
        result=call(args);require(result.returncode==0,result.stderr);identity=result.stdout.strip()
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0]
        from run_osm_country_screen_v1 import isolation
        isolation(observed,'controls')
        save('container-initial.json',{'Image':observed['Image'],'HostConfig':observed['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in observed['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began<870,'Diagnostic host deadline')
                require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<64*MIB,'Diagnostic owned output cap');time.sleep(.5)
        state=json.loads(call(['docker','inspect',identity]).stdout)[0]
        save('container-result.json',{'State':state['State'],'clientExitCode':child.returncode})
        require(child.returncode==state['State']['ExitCode']==0 and not state['State']['OOMKilled'],'Diagnostic worker exit/OOM');success=True
    except BaseException as error:save('driver-failure.json',{'error':str(error),'status':'stopped'})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save('run-summary.json',{'status':'captured' if success else 'stopped','hostSeconds':time.monotonic()-began,'networkRequests':0,'wholeSourceQualified':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(hashlib.sha256(Path(args.recipe).read_bytes()).hexdigest()==args.sha256,'Diagnostic exact recipe')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_text()),'/work') if args.worker else driver(args.recipe,args.sha256))
