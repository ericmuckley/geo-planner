"""Load typed water tables with independent complete source-byte shadows."""
from array import array
import ctypes
import hashlib
import struct
import time

from coarse_osm_country_wire_v4 import CALLBACK,decode_frame
from coarse_osm_water_coordinates_v1 import COUNTERS,WaterCoordinates
from coarse_osm_water_endpoints_v1 import frames
from coarse_osm_water_reference_store_v1 import Reader
from coarse_timing_input import require


def load_coordinates(catalog,artifact,reference_root,index_report,coordinate_root,coordinate_report,check):
    capture=coordinate_report['coordinates']['capture'];stored=coordinate_report['coordinates']['stored']
    require(capture['requested']==capture['present'] and capture['missing']==0 and not stored['missing']['parts'],'Water catalog requires complete present geometry; missing coordinates stay explicit')
    def chunks():
        with Reader(reference_root,index_report) as reader:
            while raw:=reader.read(1048576):yield raw
            require(reader.finished,'Water catalog complete requested-ID stream')
    engine=WaterCoordinates(*artifact,requested=capture['requested'],id_chunks=chunks,store=None)
    lib=engine.library;require(lib.gp_water_coords_audit_begin(engine.requested)==0,'Water catalog independent decoder begin')
    digest=hashlib.sha256();total=0;errors=[]
    try:
        engine.load_ids('gp_water_coords_audit')
        def receive(_,event,data,size):
            nonlocal total
            try:
                check();require(event==32 and 0<size<=1048576 and size%16==0,'Water catalog all-present canonical decoder event')
                raw=ctypes.string_at(data,size);catalog.append_points(raw);digest.update(raw);total+=size;return 0
            except BaseException as error:errors.append(error);return -1
        callback=CALLBACK(receive);error=ctypes.create_string_buffer(512)
        with Reader(coordinate_root,stored['encoded']) as reader:
            while raw:=reader.read(1048576):
                check();buffer=ctypes.create_string_buffer(raw);code=lib.gp_water_coords_audit_feed(buffer,len(raw),callback,None,error,len(error))
                if errors:raise errors[0]
                require(code==0,'Water catalog independent coordinate decode: '+error.value.decode('ascii'))
            require(reader.finished,'Water catalog complete coordinate EOF')
        values=(ctypes.c_uint64*len(COUNTERS))();code=lib.gp_water_coords_audit_finish(values,len(values),callback,None,error,len(error))
        if errors:raise errors[0]
        require(code==0 and dict(zip(COUNTERS,map(int,values)))==capture,'Water catalog complete independent ID/coordinate partition')
        require({'bytes':total,'sha256':digest.hexdigest()}==stored['sourceShadow'],'Water catalog decoded exact original source-coordinate shadow')
    finally:lib.gp_water_coords_audit_release()
    # The 813MB country decoder index is gone before any way-table allocation.
    retained=catalog.seal('points');require(retained==stored['sourceShadow'],'Water catalog every retained coordinate independently exact')
    require(catalog.stats()['ways']==0 and catalog.stats()['backingBytes']==capture['present']*16,'Water catalog phase lifetime/backing')
    return {'allSourceCoordinateBytesCompared':total,'canonicalSourceShadowSha256':digest.hexdigest(),'independentDecoderReleasedBeforeWays':True}


def load_catalog(catalog,artifact,reference_root,reference_report,coordinate_root,coordinate_report,check=lambda:None):
    began=time.monotonic();references=reference_report['water']['referenceStore'];capture=coordinate_report['coordinates']['capture']
    expected=reference_report['water']['referenceCapture'];ways=expected['ways'];occurrences=expected['references']
    catalog.begin(capture['present'],ways,occurrences)
    coordinates=load_coordinates(catalog,artifact,reference_root,references['nodes'],coordinate_root,coordinate_report,check)
    coordinate_seconds=time.monotonic()-began;way_started=time.monotonic()
    with Reader(reference_root,references['ways']) as reader:
        for raw in frames(reader):check();catalog.append_way(raw)
        require(reader.finished,'Water catalog full saved-way load EOF')
    loaded_seconds=time.monotonic()-way_started;audit_started=time.monotonic()
    digest=hashlib.sha256();total=count=refs=tagged=0;selected_ids=array('Q');selected_counts=array('I')
    with Reader(reference_root,references['ways']) as reader:
        for raw in frames(reader):
            check();row=decode_frame(raw);require(row['type']=='way','Water catalog independent source-way type')
            tags=row['tags'];nodes=row['nodes'];selected=tags.get('natural')=='water' or tags.get('waterway')=='riverbank' or tags.get('landuse')=='reservoir'
            wire=struct.pack('<QIB',row['id'],len(nodes),int(selected))+struct.pack('<'+str(len(nodes))+'Q',*nodes)
            digest.update(wire);total+=len(wire);count+=1;refs+=len(nodes);tagged+=selected
            if selected:selected_ids.append(row['id']);selected_counts.append(len(nodes))
        require(reader.finished,'Water catalog independent all-way field audit EOF')
    retained=catalog.seal('ways')
    require(retained=={'bytes':total,'sha256':digest.hexdigest()},'Water catalog every retained way/selector/reference source byte independently exact')
    stats=catalog.stats();require((stats['nodes'],stats['ways'],stats['references'],stats['taggedWays'],stats['coordinatesSealed'],stats['waysSealed'],stats['failed'])==
                               (capture['present'],ways,occurrences,tagged,1,1,0) and count==ways and refs==occurrences,'Water catalog complete population')
    return {'coordinates':coordinates,'waySourceShadow':retained,'statistics':stats,
            'coordinateLoadAndIndependentShadowSeconds':coordinate_seconds,'wayLoadSeconds':loaded_seconds,
            'independentAllWaySourceFieldAuditSeconds':time.monotonic()-audit_started,
            'loadAndAllIndependentAuditsSeconds':time.monotonic()-began},selected_ids,selected_counts
