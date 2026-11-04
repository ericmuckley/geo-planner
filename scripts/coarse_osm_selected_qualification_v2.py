"""Synthetic disk-selection proof; never mounts or opens national source data."""
from copy import deepcopy
import gzip
import hashlib
import importlib
from pathlib import Path
import time
import unittest

from coarse_osm_build_v1 import sha
from coarse_osm_bulk import extract as reference_extract
from coarse_osm_country_screen_v1 import BoundedCodec,OwnedStorage
from coarse_osm_country_screen_v1_test import binding
from coarse_osm_country_screen_v7 import NativeScreen
from coarse_osm_country_wire_v4 import reference_seal
from coarse_osm_filtered_extract_v3 import extract
from coarse_osm_native_lock_v1 import save
from coarse_osm_native_smoke import fixture_records,write_xml,STATE
from coarse_osm_projector_v1 import EncodedIndex
from coarse_osm_records import canonical,strict_json
from coarse_osm_revalidated_index_v1 import SourceIndex
from coarse_osm_window_cells_v1 import Cells,SCALE
from coarse_osm_window_codec_v2 import Codec
from coarse_osm_window_masks_v1 import Masks
from coarse_timing_input import require

SELECTED=2000000
FIRST_ID=2**63-SELECTED


def synthetic_node(ordinal):
    return {'type':'node','id':FIRST_ID+ordinal,'version':1,'timestamp':STATE,'visible':True,'tags':{},
            'lon':(ordinal%20001-10000)/SCALE,'lat':(ordinal%10001-5000)/SCALE}


def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item.id()


def tiny_proof(root,artifact,check):
    import osmium
    proposal=strict_json(Path('/docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json').read_bytes())
    proposal['source']['proposedPublisherReplicationStateUtc']=STATE
    proposal['windows']=[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}]
    proposal['proposedCaps'].update(sqliteIndexBytesEach=1048576,sqliteMaxPagesEach=256,sqliteCacheBytesEach=8192,workingBytesIncludingTmp=67108864,tmpBytes=65536,
        pythonSelectionStateBytes=64*1024**2,retainedNativeObjectBytes=1048576,normalizedExtractBytes=1048576,
        scanNodesPerPass=10000,scanWaysPerPass=10000,scanRelationsPerPass=10000,scanObjectVisitsTotal=100000,wallSeconds=60)
    rows=fixture_records();xml=root/'tiny.osm';pbf=root/'tiny.pbf';write_xml(xml,rows)
    header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
    with osmium.SimpleWriter(str(pbf),header=header,bufsz=65536) as writer:
        for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
    fine=EncodedIndex(root/'fine-input',OwnedStorage(root),codec=BoundedCodec(*artifact,row_budget=10000),index_limit=1048576)
    for raw in rows:
        if raw['type']=='node':fine.add_xy(raw['id'],round(raw['lon']*SCALE),round(raw['lat']*SCALE))
    fine.finish();fine.close();manifest=strict_json((fine.root/'index.json').read_bytes())
    before={p.name:sha(p) for p in fine.root.iterdir()};readonly_views=[]
    def factory(output,storage,*,codec,index_limit,replacing=None):
        view=SourceIndex(fine.root,codec,manifest,index_limit=index_limit,replacing=replacing);readonly_views.append(view);return view
    (root/'disk-extract').mkdir();(root/'four-pass-reference').mkdir()
    engine=NativeScreen(*artifact);grid=Cells(proposal['windows'])
    state=extract(pbf,proposal,root/'disk-extract',engine=engine,cell_codec=Codec(*artifact,grid),masker=Masks(*artifact,grid),
                  expected_counts={'node':4,'way':3,'relation':2},index_factory=factory,check=check)
    require(state['status']=='passed_disk_selected_extraction_prototype','Disk tiny proof failed: '+str(state.get('error')))
    reference=reference_extract(lambda:iter(deepcopy(rows)),proposal,root/'four-pass-reference',source_identity={'publisherStateUtc':STATE})
    require(reference['status']=='extracted_publisher_file_analysis_pending','Independent tiny reference failed: '+str(reference.get('error')))
    output=root/'disk-extract/elements.jsonl';expected=root/'four-pass-reference/elements.jsonl'
    require(output.read_bytes()==expected.read_bytes() and output.stat().st_size==1470 and sha(output)=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c','Tiny golden output drift')
    after={p.name:sha(p) for p in fine.root.iterdir()};require(before==after,'Read-only fine input changed')
    require(all(v.verification_passes==1 for v in readonly_views),'Missing whole fine input verification')
    require(all(s['closed'] and s['sealed'] and s['integrityOk'] for s in state['selectedStores']),'Selected store close/seal proof')
    save(root/'tiny-proof.json',{'state':state,'proposal':proposal,'sourceIndexViews':[v.report() for v in readonly_views],
         'inputBeforeSha256':before,'inputAfterSha256':after,'outputBytes':output.stat().st_size,'outputSha256':sha(output),
         'referenceSourceVisits':reference['scanObjectVisits'],'nativeSourceVisits':engine.visits})
    return engine.visits


def native_boundary_proof(root,artifact,check):
    import osmium
    began=time.monotonic();pbf=root/'two-million.pbf';archive=root/'two-million-fields.jsonl.gz'
    header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
    with osmium.SimpleWriter(str(pbf),header=header,bufsz=1048576) as writer:
        for ordinal in range(SELECTED):
            if ordinal%4096==0:check()
            raw=synthetic_node(ordinal)
            writer.add_node(osmium.osm.mutable.Node(id=raw['id'],version=1,timestamp=STATE,visible=True,tags={},location=(raw['lon'],raw['lat'])))
    require(pbf.stat().st_size<=64*1024**2,'Synthetic source size cap')
    source=binding(pbf);engine=NativeScreen(*artifact,aggregate_visits=SELECTED,codec_rows=2*SELECTED)
    count=raw_bytes=0;hashed=hashlib.sha256()
    with archive.open('xb') as saved:
        with gzip.GzipFile(filename='',fileobj=saved,mode='wb',mtime=0) as compressed:
            def keep(raw):
                nonlocal count,raw_bytes
                require(count<SELECTED and raw==synthetic_node(count),'Native selected full-field boundary mismatch')
                line=canonical(raw)+b'\n';require(len(line)<=256,'Synthetic full-field row cap')
                raw_bytes+=len(line);require(raw_bytes<=512*1024**2,'Synthetic full-field total cap')
                compressed.write(line);hashed.update(line);count+=1
            caps={'singleNormalizedElementBytes':4194304,'scanNodesPerPass':SELECTED,'scanWaysPerPass':1,'scanRelationsPerPass':1,
                  'scanObjectVisitsTotal':SELECTED,'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
            receipt=engine.scan(pbf,STATE,caps,source=source,selected=range(FIRST_ID,2**63),on_record=keep,
                                on_way_batch=lambda rows:require(False,'Unexpected synthetic ways'),batch_scope='all',check=check)
    require(count==SELECTED and receipt['nativeEof'] and receipt['counts']=={'node':SELECTED} and receipt['selectedNodeProjections']==receipt['witnessRows']==SELECTED,'Native selected boundary incomplete')
    def expected_rows():
        for ordinal in range(SELECTED):
            if ordinal%4096==0:check()
            yield synthetic_node(ordinal)
    require(reference_seal(expected_rows())==receipt['semanticSha256'],'Independent boundary semantic seal drift')
    require(archive.stat().st_size<=513*1024**2,'Compressed fields cap')
    proof={'selectedNodes':count,'firstId':FIRST_ID,'lastId':2**63-1,'nativeReceipt':receipt,'source':source,
           'archiveBytes':archive.stat().st_size,'archiveSha256':sha(archive),'fullFieldBytes':raw_bytes,'fullFieldSha256':hashed.hexdigest(),
           'protectedSecondsIncludingEncodingNativeComparisonAndReferenceSeal':time.monotonic()-began,
           'allSelectedFieldsCompared':True,'nationalInputRead':False,'modelChanged':False}
    save(root/'native-boundary-proof.json',proof);return engine.visits


def qualify(plan,root,check):
    root=Path(root);meta=strict_json(Path('/artifacts/result.json').read_bytes());artifact=('/artifacts/country-screen.so',meta['artifactSha256'])
    old=Path('/code/coarse_osm_country_screen_v6.cpp').read_text();new=Path('/code/coarse_osm_country_screen_v7.cpp').read_text()
    require(old.count('count<=250000')==1 and old.count('return 0x50000')==1,'Native parent constants')
    require(new==old.replace('count<=250000','count<=2000000').replace('return 0x50000','return 0x60000'),'Native change exceeds selected count and ABI')
    modules=[importlib.import_module(name) for name in plan['modules']]
    for module in modules:
        if hasattr(module,'configure_native'):module.configure_native(*artifact)
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module) for module in modules)
    require(sorted(flatten(suite))==plan['testIds'],'Disk qualification test roster drift')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'errors':len(result.errors),'failures':len(result.failures),'skipped':len(result.skipped)}
    save(root/'controls.json',controls)
    require(result.wasSuccessful() and not result.skipped,'Disk selected target controls failed/skipped')
    visits=sum(e.visits for m in modules for e in getattr(m,'ENGINES',[]))
    visits+=tiny_proof(root,artifact,check);visits+=native_boundary_proof(root,artifact,check)
    require(visits<=plan['aggregateSourceReceipts'],'Disk qualification source receipt cap')
    save(root/'result.json',{'status':'passed_disk_selected_synthetic_qualification','controls':controls,'aggregateNativeSourceReceipts':visits,
         'nationalInputRead':False,'nationalCaptureAdmitted':False,'modelChanged':False})
