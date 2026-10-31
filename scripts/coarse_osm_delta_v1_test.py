"""Synthetic format/C ABI/rolling audit controls. Never reads saved road samples."""
from copy import deepcopy
import ctypes
import hashlib
import json
from pathlib import Path
import random
import struct
import tempfile
import unittest
from unittest.mock import patch

from coarse_osm_delta_v1 import (BLOCK,ENTRY,SHARD,DIRECTORY,ROWS,MAX_ID,MAX_PAYLOAD,Index,Reader,
    ReferenceCodec,NativeCodec,Storage,encode_block,decode_block)
from coarse_osm_delta_extract_v1 import extract
from coarse_osm_bulk import extract as reference_extract, records as reference_records
from coarse_osm_compact_v1 import Index as FixedIndex, coordinate
from coarse_osm_native_smoke import fixture_records, STATE
from coarse_osm_records import canonical
from coarse_timing_input import PilotError

CODEC = None


def configure_native(path,sha):
    global CODEC
    CODEC=NativeCodec(path,sha)


class Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.serial=0
        self.codec=CODEC or ReferenceCodec()
        repo=Path(__file__).resolve().parents[1]
        self.config=json.loads((repo/'docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json').read_text())
        self.config['source']['proposedPublisherReplicationStateUtc']=STATE
        self.config['windows']=[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}]
        self.config['proposedCaps'].update(sqliteIndexBytesEach=1048576,sqliteMaxPagesEach=256,sqliteCacheBytesEach=8192,
            workingBytesIncludingTmp=33554432,tmpBytes=65536,pythonSelectionStateBytes=4194304,retainedNativeObjectBytes=1048576,
            normalizedExtractBytes=1048576,scanNodesPerPass=100,scanWaysPerPass=100,scanRelationsPerPass=100,scanObjectVisitsTotal=1200,wallSeconds=30)
    def directory(self):
        self.serial+=1;p=self.root/str(self.serial);p.mkdir();return p
    def index(self,**kwargs):return Index(self.directory()/'index',Storage(67108864,67108864),codec=self.codec,**kwargs)
    def rows(self,count):return [(i*129+1,(i%3600000001)-1800000000,(i%1800000001)-900000000) for i in range(count)]
    def built(self,rows=None,**kwargs):
        rows=self.rows(9) if rows is None else rows;index=self.index(**kwargs)
        for row in rows:index.add_xy(*row)
        index.finish();return index
    def run_extract(self,reader=None,**kwargs):
        root=self.directory();result=extract(reader or (lambda:iter(deepcopy(fixture_records()))),self.config,root,codec=self.codec,**kwargs)
        return result,root

    def test_fixed_seed_full_blocks_match_independent_codec(self):
        rng=random.Random(43781);oracle=ReferenceCodec()
        cases=[[(1,-1800000000,-900000000)],[(1,0,0),(MAX_ID,1800000000,900000000)]]
        for count in (2,3,127,4096):
            ids=sorted(rng.sample(range(1,2**62),count))
            cases.append([(i,rng.randint(-1800000000,1800000000),rng.randint(-900000000,900000000)) for i in ids])
        for rows in cases:
            payload=self.codec.encode(rows);self.assertEqual(payload,oracle.encode(rows));self.assertEqual(self.codec.decode(payload,len(rows),rows[0][0],rows[-1][0]),rows)
            self.assertEqual(decode_block(encode_block(rows,self.codec),oracle),rows)
        self.assertEqual((BLOCK.size,ENTRY.size,SHARD.size,DIRECTORY.size),(64,32,128,128))
        self.assertEqual(MAX_PAYLOAD,69623)

    def test_coordinate_bits_signed_id_edges_missing_and_duplicate_queries(self):
        rows=[(1,-1800000000,-900000000),(100,-1,1),(MAX_ID,1800000000,900000000)]
        index=self.built(rows);keys=[MAX_ID,1,100,100]
        expected=[[180.,90.],[-180.,-90.],[-.0000001,.0000001],[-.0000001,.0000001]]
        self.assertEqual(index.points(keys),expected)
        for a,b in zip(index.points(keys),expected):
            self.assertEqual(struct.pack('<dd',*a),struct.pack('<dd',*b))
        for key in (0,True,2,99,101,MAX_ID+1):
            with self.assertRaises(PilotError):index.points([key])
        with self.assertRaises(PilotError):index.points([1]*65537)
        for value,bound in [(-0.,180),(.123456789,180),(float('inf'),180),(float('nan'),90),(181.,180),(True,180)]:
            with self.assertRaises(PilotError):coordinate(value,bound)

    def test_noncanonical_zero_overlong_truncated_overflow_xy_and_last_id_refused(self):
        xy=struct.pack('<ii',0,0)
        cases=[(xy+b'\x00'+xy,2,1,2),(xy+b'\x81\x00'+xy,2,1,2),
            (xy+b'\x80'*9+xy,2,1,2),(xy+b'\x81',2,1,2),
            (xy+b'\x02'+xy,2,MAX_ID-1,MAX_ID),(xy+b'\x01'+xy+b'x',2,1,2),
            (struct.pack('<ii',1800000001,0),1,1,1),(xy,1,1,2),(xy,0,1,1)]
        for payload,count,first,last in cases:
            with self.subTest(count=count,first=first):
                with self.assertRaises(PilotError):self.codec.decode(payload,count,first,last)
        for rows in ([],[(0,0,0)],[(True,0,0)],[(1,0,0),(1,0,0)],[(2,0,0),(1,0,0)],[(MAX_ID+1,0,0)],[(1,0,900000001)]):
            with self.assertRaises(PilotError):self.codec.encode(rows)

    def test_block_flags_reserved_lengths_and_payload_sha_rejected(self):
        original=encode_block(self.rows(3),self.codec)
        for offset in (0,4,5,6,8,16,24,28,32,64):
            raw=bytearray(original);raw[offset]^=1
            with self.assertRaises(PilotError):decode_block(bytes(raw),self.codec)
        for raw in (original[:-1],original+b'x',b''):
            with self.assertRaises(PilotError):decode_block(raw,self.codec)

    def reseal(self,index,shard=None,directory=None,manifest=None):
        m=json.loads((index.root/'index.json').read_text());d=bytearray((index.root/'directory.bin').read_bytes())
        if shard is not None:
            raw=bytearray(index.path(0).read_bytes());shard(raw);index.path(0).write_bytes(raw)
            m['shards'][0]['sha256']=hashlib.sha256(raw).hexdigest()
        if directory is not None:directory(d)
        d[72:104]=hashlib.sha256(canonical(m['shards'])).digest()
        m['directory']['sha256']=hashlib.sha256(d).hexdigest();(index.root/'directory.bin').write_bytes(d)
        if manifest is not None:manifest(m)
        (index.root/'index.json').write_bytes(canonical(m)+b'\n')

    def test_resigned_shard_headers_and_directory_offsets_counts_flags_rejected(self):
        for offset in (0,8,10,12,16,20,24,32,40,48,56,88,120):
            index=self.built()
            self.reseal(index,shard=lambda r:r.__setitem__(offset,r[offset]^1))
            with self.assertRaises(PilotError):Reader(index.root,self.codec).points([1])
        for offset in (0,8,10,12,16,24,32,40,104,128,136,144,148,150,152,156):
            index=self.built();self.reseal(index,directory=lambda r:r.__setitem__(offset,r[offset]^1))
            with self.assertRaises(PilotError):Reader(index.root,self.codec).points([1])
        for mutate in (lambda m:m.update(rows=True),lambda m:m.update(blocks=-1),lambda m:m['shards'][0].update(first=0),lambda m:m.update(extra='x')):
            index=self.built();self.reseal(index,manifest=mutate)
            with self.assertRaises(PilotError):Reader(index.root,self.codec)

    def test_whole_shard_truncation_symlink_cache_and_catalog_drift_refused(self):
        for damage in ('truncate','flip','symlink','cache','catalog'):
            index=self.built();path=index.path(0);raw=path.read_bytes()
            if damage=='cache':index.points([1])
            if damage=='catalog':(index.root/'index.json').write_bytes(b'{}')
            elif damage=='symlink':
                path.unlink();(index.root/'other').write_bytes(raw);path.symlink_to(index.root/'other')
            else:path.write_bytes(raw[:-1] if damage=='truncate' else raw[:-1]+bytes([raw[-1]^1]))
            with self.assertRaises(PilotError):index.points([1])

    def test_multi_shard_rolling_rebuild_and_capped_cache(self):
        rows=self.rows(ROWS*3+7);first=self.built(rows,blocks_per_shard=1)
        first.points([rows[0][0],rows[-1][0]])
        second=Index(first.root.parent/'audit',first.storage,codec=self.codec,replacing=first,blocks_per_shard=1)
        for row in rows:second.add_xy(*row)
        second.finish()
        self.assertEqual(len(second.reader.manifest['shards']),4)
        self.assertFalse(list(first.root.glob('[0-9]*.bin')))
        self.assertEqual(second.points([rows[-1][0],rows[0][0],rows[1][0],rows[1][0]]),[[r[1]/10000000,r[2]/10000000] for r in [rows[-1],rows[0],rows[1],rows[1]]])
        self.assertLessEqual(len(second.reader.cache),64)
        self.assertTrue(all(a.itemsize==8 and b.itemsize==4 for a,b in second.reader.cache.values()))
        second.reader.verify_catalogs()

    def test_cache_eviction_and_verified_shard_block_reads_stay_bounded(self):
        index=self.index()
        for identity in range(1,67):
            index.add_xy(identity,identity,0);index.flush_block()
        index.finish();self.assertEqual(index.reader.manifest['blocks'],66)
        index.points(list(range(1,67)))
        self.assertEqual(len(index.reader.cache),64)
        self.assertNotIn(0,index.reader.cache)
        before=index.reader.loaded_bytes;index.points([1])
        self.assertLess(index.reader.loaded_bytes-before,index.reader.manifest['shards'][0]['bytes'])
        self.assertLessEqual(sum(a.itemsize*len(a)+b.itemsize*len(b) for a,b in index.reader.cache.values()),4194304)
        with self.assertRaises(PilotError):Reader(index.root,self.codec,cache_blocks=65)

    def test_reader_rejects_nonbinary_and_extra_directory_or_shard_counts(self):
        for mutation in (lambda m:m['shards'].append(deepcopy(m['shards'][0])),lambda m:m['directory'].update(bytes=True),
            lambda m:m['shards'][0].update(bytes=-1),lambda m:m.update(rows=0),lambda m:m.update(shards=[])):
            index=self.built();self.reseal(index,manifest=mutation)
            with self.assertRaises(PilotError):Reader(index.root,self.codec)

    def test_corrupt_or_source_drifted_primary_never_deleted(self):
        for drift in ('source','primary','fewer'):
            rows=self.rows(7);first=self.built(rows);second=Index(first.root.parent/'audit',first.storage,codec=self.codec,replacing=first)
            if drift=='primary':
                p=first.path(0);raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            changed=deepcopy(rows)
            if drift=='source':changed[0]=(changed[0][0],0,0)
            if drift=='fewer':changed.pop()
            with self.assertRaises(PilotError):
                for row in changed:second.add_xy(*row)
                second.finish()
            self.assertTrue(first.path(0).exists());self.assertFalse((second.root/'index.json').exists())

    def test_file_index_catalog_shared_storage_and_writer_state_limits(self):
        for storage,limit,catalog in [(Storage(32,10000),10000,1000),(Storage(10000,32),10000,1000),(Storage(10000,10000),32,1000),(Storage(10000,10000),10000,32)]:
            index=Index(self.directory()/'index',storage,codec=self.codec,index_limit=limit,catalog_limit=catalog)
            index.add_xy(1,0,0)
            with self.assertRaises(PilotError):index.finish()
            self.assertLessEqual(storage.live,storage.limit)
        index=self.index();index.add_xy(2,0,0)
        for key in (1,2,True,MAX_ID+1):
            with self.assertRaises(PilotError):index.add_xy(key,0,0)
        with self.assertRaises(PilotError):index.points([2])
        index.finish();index.finish();index.close();index.close()
        with self.assertRaises(PilotError):index.points([2])
        with self.assertRaises(FileExistsError):Index(index.root,index.storage,codec=self.codec)
        empty=self.built([]);self.assertEqual(empty.points([]),[])
        with self.assertRaises(PilotError):empty.points([1])

    def test_two_pass_native_index_outputs_match_four_pass_reference(self):
        result,root=self.run_extract();self.assertEqual(result['status'],'passed_native_delta_index_synthetic',result)
        expected=self.directory();old=reference_extract(lambda:iter(fixture_records()),self.config,expected,source_identity={'publisherStateUtc':STATE})
        self.assertTrue(old['independentAuditComplete']);self.assertEqual((root/'elements.jsonl').read_bytes(),(expected/'elements.jsonl').read_bytes())
        self.assertEqual(result['scanObjectVisits'],18);self.assertTrue(result['independentAuditComplete']);self.assertFalse(result['nativeMetadataValidationQualified'])

    def test_independent_audit_detects_omitted_extra_wrong_membership_and_output(self):
        def all_removed(s):
            s.keys.clear()
            for keys in s.members.values():keys.clear()
        def way_removed(s):
            s.keys.remove(('way',1))
            for keys in s.members.values():keys.discard(('way',1))
        def node_removed(s):
            s.keys.remove(('node',2))
            for keys in s.members.values():keys.discard(('node',2))
        def extra(s):s.add('a',('node',3))
        def membership(s):s.members['b'].clear()
        for hook in (all_removed,way_removed,node_removed,extra,membership):
            state,_=self.run_extract(primary_hook=hook);self.assertEqual(state['status'],'stopped');self.assertFalse(state['independentAuditComplete'])
        def omit(selection,snapshot):yield from (r for r in reference_records(selection,snapshot) if r['element']['type']!='relation')
        with patch('coarse_osm_delta_extract_v1.records',omit):
            state,_=self.run_extract();self.assertEqual(state['status'],'stopped');self.assertIn('Independent',state['error'])

    def test_reference_validator_caps_metadata_drift_and_missing_nodes_remain_enforced(self):
        for change in ('time','duplicate','ref','copy','visits','selected','output'):
            rows=fixture_records();config=deepcopy(self.config)
            if change=='time':rows[0]['timestamp']='2026-02-30T00:00:00Z'
            elif change=='duplicate':rows[1]['id']=1
            elif change=='ref':rows[4]['nodes'][0]=999
            else:config['proposedCaps'][{'copy':'singleNormalizedElementBytes','visits':'scanObjectVisitsTotal','selected':'selectedUniqueTypedElements','output':'normalizedExtractBytes'}[change]]=1
            state=extract(lambda:iter(rows),config,self.directory(),codec=self.codec);self.assertEqual(state['status'],'stopped');self.assertFalse(state['independentAuditComplete'])
        for change in ('coordinate','unselected-tags','count'):
            calls=0
            def reader():
                nonlocal calls
                rows=fixture_records();calls+=1
                if calls==2:
                    if change=='coordinate':rows[0]['lon']+=1
                    elif change=='unselected-tags':rows[3]['tags']['drift']='yes'
                    else:rows.pop()
                return iter(rows)
            state,_=self.run_extract(reader=reader);self.assertEqual(state['status'],'stopped')

    def test_fixed_ordinary_synthetic_ids_use_less_bytes_than_id64_rows(self):
        rows=[(i+1,(i%100)*1000000,0) for i in range(20000)]
        delta=self.built(rows);fixed=FixedIndex(self.directory()/'fixed',Storage(67108864,67108864))
        for i,x,y in rows:fixed.add({'id':i,'lon':x/10000000,'lat':y/10000000})
        fixed.finish()
        self.assertLess(delta.generated_bytes,fixed.generated_bytes)
        self.assertEqual(delta.points([1,10000,20000]),fixed.points([1,10000,20000]))

    def test_delta_driver_disallows_source_mounts_and_wrong_phase_limits(self):
        from run_osm_delta_v1 import CAPS,IMAGE,OUTPUT,FLAGS,ASSET_ROOT,PROPOSAL,validate,isolation
        mounts={PROPOSAL:'/'+PROPOSAL,'scripts/coarse_osm_delta_v1.cpp':'/code/coarse_osm_delta_v1.cpp'}
        plan={'phase':'offline_native_delta_v1','caps':deepcopy(CAPS),'imageId':IMAGE,'imagePull':'never','output':OUTPUT,'phases':['build','controls'],
            'network':'none','flags':FLAGS,'rootfs':{'path':ASSET_ROOT,'portable':{'portableTreeSha256':'a64ef22d93c8b49689ccfefe09c67a62e67422cb84c6edb86089533fb33ebd72'}},
            'mounts':mounts,'inputs':{p:'hash' for p in mounts},'workerFiles':{p:'hash' for p in mounts.values()}}
        validate(plan)
        for mutation in (lambda p:p.update(network='bridge'),lambda p:p['mounts'].update({'data/road.pbf':'/code/road.pbf'}),
            lambda p:p['rootfs'].update(path='other'),lambda p:p['caps'].update(nativeCodecRows=2000001)):
            bad=deepcopy(plan);mutation(bad)
            with self.assertRaises(PilotError):validate(bad)
        for phase in ('build','controls'):
            config={'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,
                'Tmpfs':{('/builder/tmp' if phase=='build' else '/tmp'):'rw,size=256m'},'CapAdd':['CAP_SYS_CHROOT'] if phase=='build' else [],'CapDrop':['ALL'],
                'SecurityOpt':['no-new-privileges'],'Ulimits':[{'Name':'core','Soft':0,'Hard':0},{'Name':'fsize','Soft':67108864,'Hard':67108864}]}
            obj={'Image':IMAGE,'HostConfig':config,'Mounts':[{'Destination':'/code/a.py','RW':False}]};isolation(obj,phase)
            obj['Mounts'][0]['RW']=True
            with self.assertRaises(PilotError):isolation(obj,phase)
            obj['Mounts'][0]['RW']=False;config['NetworkMode']='bridge'
            with self.assertRaises(PilotError):isolation(obj,phase)

    def test_native_c_abi_null_arguments_and_short_buffers_refuse_without_writes(self):
        if not isinstance(self.codec,NativeCodec):self.skipTest('Compiled target artifact required')
        ids=(ctypes.c_int64*2)(1,2);xy=(ctypes.c_int32*4)(0,0,0,0);out=(ctypes.c_uint8*64)(*([0x55]*64));used=ctypes.c_uint32(999)
        self.assertNotEqual(self.codec.enc(None,xy,2,out,64,ctypes.byref(used)),0);self.assertEqual(used.value,0)
        self.assertNotEqual(self.codec.enc(ids,xy,2,out,1,ctypes.byref(used)),0);self.assertEqual(bytes(out),b'\x55'*64)
        ids[1]=1
        self.assertNotEqual(self.codec.enc(ids,xy,2,out,64,ctypes.byref(used)),0);self.assertEqual(bytes(out),b'\x55'*64)
        xy[0]=1800000001;ids[1]=2
        self.assertNotEqual(self.codec.enc(ids,xy,2,out,64,ctypes.byref(used)),0);self.assertEqual(bytes(out),b'\x55'*64)
        self.assertNotEqual(self.codec.enc(ids,xy,4097,out,64,ctypes.byref(used)),0)
        self.assertNotEqual(self.codec.dec(None,0,1,1,1,ids,xy,2),0)
        raw=(ctypes.c_uint8*8)()
        self.assertNotEqual(self.codec.dec(raw,8,1,1,1,ids,xy,0),0)


if __name__=='__main__':unittest.main()
