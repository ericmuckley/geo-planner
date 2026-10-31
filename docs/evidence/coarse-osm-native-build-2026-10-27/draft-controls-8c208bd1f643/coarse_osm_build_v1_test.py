"""Synthetic artifact/network/tar/chroot controls; no real endpoint or road input."""
from contextlib import nullcontext
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from urllib.parse import urlencode

from coarse_osm_build_v1 import (CAPS, LOCK, LOCK_SHA, Download, acquire, expand_layer, extract_source,
    inventory, safe_name, target, link_valid, source_url, prepare)
from coarse_osm_native_lock_v1_test import Reply, Transport
from coarse_osm_native_lock_v2 import QUERY_KEYS, cdn_path, config_url
from coarse_timing_input import PilotError

SECRET='PRIVATE-ARTIFACT-URL-MUST-NOT-PERSIST'


def tar_bytes(rows):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w',format=tarfile.PAX_FORMAT) as archive:
        for name,kind,body in rows:
            item=tarfile.TarInfo(name);item.mode=0o755 if kind=='dir' else 0o644
            if kind=='dir':item.type=tarfile.DIRTYPE
            elif kind=='symlink':item.type=tarfile.SYMTYPE;item.linkname=body
            elif kind=='hardlink':item.type=tarfile.LNKTYPE;item.linkname=body
            elif kind=='device':item.type=tarfile.CHRTYPE
            else:item.size=len(body)
            archive.addfile(item,io.BytesIO(body) if kind=='file' else None)
    return output.getvalue()


def layer(raw):return {'mediaType':'application/vnd.docker.image.rootfs.diff.tar.gzip','size':len(raw),'digest':'sha256:'+hashlib.sha256(raw).hexdigest()}
def signed(desc):return 'https://cdn01.quay.io'+cdn_path(desc)+'?'+urlencode({k:SECRET for k in QUERY_KEYS})


class Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.number=0
    def directory(self):
        self.number+=1;p=self.root/str(self.number);p.mkdir();return p
    def fixture(self):
        raw=gzip.compress(tar_bytes([('usr','dir',b''),('usr/file','file',b'hello')]))
        source={'repository':'osmcode/libosmium','commit':'1'*40,'selectedFiles':[{'path':'LICENSE','mode':'100644','type':'blob','size':5,'sha':hashlib.sha1(b'blob 5\0hello').hexdigest()}]}
        return raw,{'image':{'layers':[layer(raw)],'diffIds':['sha256:'+hashlib.sha256(gzip.decompress(raw)).hexdigest()]},'sources':[source]}
    def meter(self,replies,lock,**kwargs):return Download(self.directory()/'http',lock,transport=Transport(replies),alarm=lambda s:nullcontext(),**kwargs)
    def private_files(self,root):
        for p in root.rglob('*'):
            if p.is_file() and not p.is_symlink():self.assertNotIn(SECRET.encode(),p.read_bytes(),str(p))

    def test_exact_origin_and_cdn_download_identities_no_auth_or_private_files(self):
        raw,lock=self.fixture();desc=lock['image']['layers'][0]
        meter=self.meter([Reply(SECRET.encode(),302,[('Location',signed(desc)),('Set-Cookie',SECRET)]),Reply(raw)],lock)
        path,status,url=meter.fetch(config_url(desc),'origin',desc);self.assertIsNone(path);self.assertEqual(status,302)
        path,status,_=meter.fetch(url,'cdn',desc);self.assertEqual(path.read_bytes(),raw);self.assertEqual(status,200)
        self.assertEqual([(u,k) for u,k,_ in meter.transport.calls],[(config_url(desc),'origin'),(signed(desc),'cdn')])
        self.assertTrue(all(not {'Authorization','Cookie'}&set(h) for _,_,h in meter.transport.calls));self.private_files(meter.root)
        self.assertEqual(meter.bytes,len(raw)+len(SECRET))

    def test_wrong_layer_and_redirects_refused_without_any_widening(self):
        raw,lock=self.fixture();desc=lock['image']['layers'][0]
        meter=self.meter([],lock)
        with self.assertRaises(PilotError):meter.fetch(config_url(desc).replace(desc['digest'],'sha256:'+'e'*64),'origin',desc)
        with self.assertRaises(PilotError):meter.fetch(config_url(dict(desc,digest='sha256:'+'e'*64)),'origin',dict(desc,digest='sha256:'+'e'*64))
        self.assertFalse(meter.transport.calls)
        for url in [signed(desc).replace('cdn01.quay.io','evil.test'),signed(desc).replace('cdn01.quay.io','cdn01.quay.io:443'),signed(desc)+'&extra=bad',signed(desc)+'#fragment']:
            meter=self.meter([Reply(SECRET.encode(),302,[('Location',url)])],lock)
            with self.assertRaises(PilotError):meter.fetch(config_url(desc),'origin',desc)
            self.assertEqual(len(meter.transport.calls),1);self.private_files(meter.root)

    def test_http_partial_hash_header_open_and_close_errors_are_private(self):
        raw,lock=self.fixture();desc=lock['image']['layers'][0]
        class CloseError(Reply):
            def close(self):super().close();raise ValueError(SECRET)
        for reply in [Reply(SECRET.encode(),403),Reply(b'x'*len(raw)),Reply(raw[:-1]),TimeoutError(SECRET),
            Reply(b'',length=False,partial=SECRET.encode()),Reply(raw,headers=[('Content-Encoding',SECRET)]),CloseError(SECRET.encode(),403)]:
            meter=self.meter([reply],lock)
            try:meter.fetch(config_url(desc),'origin',desc)
            except Exception as error:self.assertNotIn(SECRET,str(error))
            else:self.assertEqual(reply.status,403)
            self.private_files(meter.root)
            if isinstance(reply,Reply):self.assertTrue(reply.closed)

    def test_aggregate_request_deadline_and_unknown_length_caps(self):
        raw,lock=self.fixture();desc=lock['image']['layers'][0]
        for caps in [dict(CAPS,attempts=0),dict(CAPS,builderBodyBytes=1),dict(CAPS,totalBodyBytes=1)]:
            meter=self.meter([Reply(raw)],lock,caps=caps)
            with self.assertRaises(PilotError):meter.fetch(config_url(desc),'origin',desc)
            self.assertLessEqual(meter.bytes,caps['totalBodyBytes'])
        meter=self.meter([Reply(b'x'*10,length=False)],lock,caps=dict(CAPS,sourceBodyBytesEach=4))
        with self.assertRaises(PilotError):meter.fetch(source_url(lock['sources'][0]),'archive',lock['sources'][0])
        self.assertEqual(meter.bytes,4)
        clock=[0];meter=self.meter([],lock,clock=lambda:clock[0]);clock[0]=CAPS['workSeconds']
        with self.assertRaises(PilotError):meter.fetch(config_url(desc),'origin',desc)
        self.assertFalse(meter.transport.calls)

    def test_acquisition_fixed_sequence_no_metadata_and_partial_source_stop(self):
        raw,lock=self.fixture();source=lock['sources'][0];archive=gzip.compress(tar_bytes([(f'libosmium-{source["commit"]}','dir',b''),(f'libosmium-{source["commit"]}/LICENSE','file',b'hello')]))
        root=self.directory();transport=Transport([Reply(raw),Reply(archive)])
        self.assertEqual(acquire(root,lock,transport=transport,alarm=lambda s:nullcontext()),0)
        self.assertEqual([(u,k) for u,k,_ in transport.calls],[(config_url(lock['image']['layers'][0]),'origin'),(source_url(source),'archive')])
        root=self.directory();transport=Transport([Reply(raw),Reply(SECRET.encode(),302,[('Location','https://other.test/archive')])])
        self.assertEqual(acquire(root,lock,transport=transport,alarm=lambda s:nullcontext()),2)
        state=json.loads((root/'result.json').read_text());self.assertEqual(len(state['layers']),1);self.assertEqual(state['sources'],[]);self.private_files(root)

    def apply(self,rows,root=None,diff=None,limit=1048576):
        raw=tar_bytes(rows);path=self.directory()/'layer.gz';path.write_bytes(gzip.compress(raw));root=root or self.directory()
        result=expand_layer(path,root,diff or 'sha256:'+hashlib.sha256(raw).hexdigest(),limit)
        return root,result

    def test_regular_dirs_links_and_two_pass_diff_validation(self):
        root,result=self.apply([('usr','dir',b''),('usr/a','file',b'hello'),('usr/b','hardlink','usr/a'),('bin','symlink','usr')])
        self.assertEqual((root/'usr/a').read_bytes(),b'hello');self.assertEqual((root/'usr/b').read_bytes(),b'hello');self.assertEqual((root/'bin').readlink(),Path('usr'))
        self.assertEqual(result['entries'],4);self.assertEqual(result['fileBytesWritten'],5)
        root=self.directory()
        with self.assertRaises(PilotError):self.apply([('file','file',b'hello')],root,diff='sha256:'+'e'*64)
        self.assertEqual(list(root.iterdir()),[])

    def test_whiteouts_apply_before_new_layer_entries_and_opaque_preserves_new(self):
        root,_=self.apply([('d','dir',b''),('d/old','file',b'old'),('same','file',b'old')])
        self.apply([('same','file',b'new'),('d/new','file',b'new'),('d/.wh..wh..opq','file',b''),('.wh.same','file',b'')],root)
        self.assertEqual((root/'same').read_bytes(),b'new');self.assertFalse((root/'d/old').exists());self.assertEqual((root/'d/new').read_bytes(),b'new')

    def test_traversal_symlink_ancestor_duplicate_special_hardlink_and_expansion_refusals(self):
        variants=[[('../escape','file',b'x')],[('/absolute','file',b'x')],[('a','file',b'x'),('a','file',b'y')],
            [('a','device',b'')],[('a','symlink','../../outside')],[('a','hardlink','absent')],
            [('a','symlink','usr'),('a/file','file',b'x')],[('.wh..wh.bad','file',b'')],[('.wh.a','file',b'x')]]
        for rows in variants:
            with self.subTest(rows=rows):
                with self.assertRaises((PilotError,FileNotFoundError)):self.apply(rows)
        with self.assertRaises(PilotError):self.apply([('a','file',b'x'*1000)],limit=512)
        self.assertFalse((self.root/'escape').exists())

    def test_source_archive_exact_commit_blob_modes_and_complete_selection(self):
        _,lock=self.fixture();source=lock['sources'][0];prefix='libosmium-'+source['commit']
        for rows,passes in [([(prefix,'dir',b''),(prefix+'/LICENSE','file',b'hello')],True),
            ([(prefix+'/LICENSE','file',b'wrong')],False),([('wrong/LICENSE','file',b'hello')],False),
            ([(prefix+'/LICENSE','symlink','other')],False),([(prefix+'/other','file',b'hello')],False),
            ([(prefix+'/LICENSE','file',b'hello'),(prefix+'/include/osmium/extra.hpp','file',b'x')],False)]:
            path=self.directory()/'source.gz';path.write_bytes(gzip.compress(tar_bytes(rows)));root=self.directory()/'selected'
            if passes:
                value=extract_source(path,root,source);self.assertTrue(value['gitBlobIdentitiesVerified']);self.assertEqual((root/'LICENSE').read_bytes(),b'hello')
            else:
                with self.assertRaises(PilotError):extract_source(path,root,source)

    def test_inventory_never_follows_external_symlinks_and_detects_changes(self):
        root=self.directory();(root/'a').write_bytes(b'hello');(root/'external').symlink_to('/not/a/real/path')
        first=inventory(root);self.assertEqual(first['files'],1);self.assertEqual(first['logicalFileBytes'],5)
        (root/'a').write_bytes(b'world');self.assertNotEqual(inventory(root)['treeSha256'],first['treeSha256'])
        for path in ('../bad','/bad','a//b','a/./b','a\\b'):
            with self.assertRaises(PilotError):safe_name(path)
        with self.assertRaises(PilotError):target(root,'external/file')
        with self.assertRaises(PilotError):link_valid('a','../../outside')

    def test_prepare_accepts_only_acquired_identity_checked_artifacts(self):
        root=self.directory();downloads=self.directory();(downloads/'result.json').write_text('{"status":"stopped"}')
        _,lock=self.fixture();self.assertEqual(prepare(root,downloads,lock),2)
        self.assertFalse((root/'rootfs').exists())

    def test_phase_isolation_and_plan_input_or_command_drift(self):
        from run_osm_build_v1 import IMAGE, OUTPUT, COMPILER, FLAGS, ENV, validate, isolation
        plan={'phase':'native_build_closure_v1','caps':deepcopy(CAPS),'imageId':IMAGE,'imagePull':'never','output':OUTPUT,
            'lock':{'path':LOCK,'sha256':LOCK_SHA},'phases':{'controls':'none','acquire':'bridge','prepare':'none','build':'none','abi':'none'},
            'mounts':{LOCK:'/inputs/lock.json'},'inputs':{LOCK:LOCK_SHA},'workerFiles':{'/inputs/lock.json':LOCK_SHA},'compiler':COMPILER,'flags':FLAGS,'compilerEnvironment':ENV}
        validate(plan)
        for mutation in [lambda p:p['caps'].update(attempts=53),lambda p:p.update(compiler='/usr/bin/other'),lambda p:p['mounts'].update({'data/roads.pbf':'/inputs/roads.pbf'})]:
            bad=deepcopy(plan);mutation(bad)
            with self.assertRaises((PilotError,KeyError)):validate(bad)
        for phase,network in plan['phases'].items():
            obj={'Image':IMAGE,'HostConfig':{'NetworkMode':network,'Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,
                'Tmpfs':{('/builder/tmp' if phase=='build' else '/tmp'):'rw,size=256m'},'CapAdd':['SYS_CHROOT'] if phase in ('controls','build') else [],'Ulimits':[{'Name':'core','Soft':0,'Hard':0},{'Name':'fsize','Soft':1073741824,'Hard':1073741824}]},'Mounts':[{'Destination':'/code/file.py','RW':False}]}
            isolation(obj,network,phase);obj['Mounts'][0]['RW']=True
            with self.assertRaises(PilotError):isolation(obj,network,phase)

    @unittest.skipUnless(sys.platform=='linux','Actual Linux chroot/capability control')
    def test_actual_chroot_clears_capabilities_and_hides_outside_files(self):
        root=self.directory();(root/'work').mkdir();(root/'marker').write_text('inside')
        code='import sys;sys.path.insert(0,sys.argv[1]);from run_osm_build_v1 import enter_builder;enter_builder(sys.argv[2]);import os;assert os.getcwd()=="/work" and sorted(os.listdir("/"))==["marker","work"]'
        result=subprocess.run([sys.executable,'-B','-c',code,str(Path(__file__).parent),str(root)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
