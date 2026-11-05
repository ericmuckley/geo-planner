"""Derive bounded water data from saved accepted geometry; no routing policy."""
import gzip
import hashlib
import json
from pathlib import Path
import time

from assemble_osm_water_polygons_v1 import FEATURE,RING
from coarse_osm_water_reference_store_v1 import Reader
from coarse_timing_input import require


def sha(raw):return hashlib.sha256(raw).hexdigest()


def write_plane(root,name,raw,cells):
    require(len(raw)==(cells+7)//8 and (cells%8==0 or raw[-1]>>(cells%8)==0),'Water raster exact plane size/zero padding')
    encoded=gzip.compress(raw,compresslevel=9,mtime=0)
    require(len(encoded)<=len(raw)+1048576,'Water raster compressed plane cap')
    with (root/(name+'.bits')).open('xb') as f:f.write(raw)
    with (root/(name+'.bits.gz')).open('xb') as f:f.write(encoded)
    # Independent standard gzip decode and complete raw-file reopen, not a
    # native buffer alias or a comparison of only compressed checksums.
    with gzip.open(root/(name+'.bits.gz'),'rb') as f:
        decoded=f.read(len(raw)+1);require(not f.read(1),'Water raster compressed EOF')
    require(decoded==raw==(root/(name+'.bits')).read_bytes(),'Water raster every raw/compressed plane byte exact')
    return {'file':name+'.bits.gz','rawFile':name+'.bits','rawBytes':len(raw),'rawSha256':sha(raw),
            'compressedBytes':len(encoded),'compressedSha256':sha(encoded),'setCells':sum(v.bit_count() for v in raw)}


def prepare(root,engine,geometry_root,polygon_report,exclusion_report,grid,check=lambda:None):
    began=time.monotonic();root=Path(root);x,y,step,width,height=grid
    engine.begin(*grid);features=rings=points=0;last_kind=last_identity=0
    with Reader(geometry_root,polygon_report['polygons']['geometryStore']) as reader:
        while raw:=reader.read(FEATURE.size):
            check();require(len(raw)==FEATURE.size,'Water raster complete saved feature header')
            kind,identity,count=FEATURE.unpack(raw)
            require(kind in (1,2) and kind>=last_kind and identity>0 and 0<count<=100000,'Water raster saved feature fields/order')
            if kind==last_kind:require(identity>last_identity,'Water raster source feature identity order')
            last_kind,last_identity=kind,identity;engine.call('feature',count);features+=1
            for _ in range(count):
                raw=reader.read(RING.size);require(len(raw)==RING.size,'Water raster complete saved ring header')
                role,parent,size=RING.unpack(raw);require(4<=size<=2000000,'Water raster source ring size')
                engine.call('ring',role,parent,size);remaining=size;rings+=1;points+=size
                while remaining:
                    amount=min(remaining,65536);raw=reader.read(amount*16)
                    require(len(raw)==amount*16,'Water raster complete canonical native/E7 chunk');engine.append_points(raw);remaining-=amount
            engine.call('feature_finish')
        require(reader.finished,'Water raster complete bound source geometry EOF')
    expected=polygon_report['polygons']
    require((features,rings,points)==(expected['acceptedFeatures'],expected['acceptedRings'],expected['sourcePointsIndependentlyReplayed']),'Water raster exact complete accepted population')
    exclusions=exclusion_report['exclusions'];known=incomplete_known=0
    require(len(exclusions['excludedFeatures'])==exclusions['excludedStandaloneWays']+exclusions['excludedRootRelations'],'Water raster every excluded feature retained')
    for feature in exclusions['excludedFeatures']:
        check();bounds=feature['knownSourceBoundsE7']
        if bounds is not None:
            engine.box(bounds,feature['allReferencedSourceGeometryBounded']);known+=1;incomplete_known+=not feature['allReferencedSourceGeometryBounded']
    engine.call('finish',features,rings,points,known,incomplete_known)
    stats=engine.stats();require(stats['nativeBackingBytes']==stats['planeBytes']==2*((width*height+7)//8),'Water raster scratch released/exact final backing')
    raster_seconds=time.monotonic()-began;output_started=time.monotonic();water,uncertain=engine.planes();check()
    planes={'water':write_plane(root,'water-center',water,width*height),'uncertainty':write_plane(root,'source-uncertainty',uncertain,width*height)}
    unknown=exclusions['unboundedOrSourceIncompleteFeatures']
    require(sum(not f['allReferencedSourceGeometryBounded'] for f in exclusions['excludedFeatures'])==len(unknown),'Water raster complete source-uncertainty metadata')
    manifest={'format':'exact-water-centers-and-source-uncertainty-v1','grid':{'xE7':x,'yE7':y,'stepE7':step,'columns':width,'rows':height,'cells':width*height,'bitOrder':'row-major-lsb-first'},
              'planes':planes,'sourceCounts':{'features':features,'rings':rings,'points':points,'excludedFeatures':len(exclusions['excludedFeatures']),'knownExcludedBounds':known},
              'sourceIncompleteFeatures':unknown,'sourceGeometryCompletelyBounded':not unknown,
              'semantics':'Closed accepted planar source water at centers; uncertainty includes every closed cell touched by a source edge/known excluded bound. Source missing geometry remains globally unqualified. No mask/land/connector/routing interpretation.'}
    encoded=(json.dumps(manifest,indent=2,allow_nan=False)+'\n').encode();require(len(encoded)<=1048576,'Water raster manifest cap')
    with (root/'manifest.json').open('xb') as f:f.write(encoded)
    require(json.loads((root/'manifest.json').read_bytes())==manifest,'Water raster manifest exact reopen')
    return {'statistics':stats,'manifestSha256':sha(encoded),'manifest':manifest,
            'sourceReadRasterizationAndScratchReleaseSeconds':raster_seconds,
            'planeExportCompressionAndEveryByteReopenSeconds':time.monotonic()-output_started,
            'totalSecondsIncludingSourceRasterAndOutputChecks':time.monotonic()-began,
            'allCompressedAndRawPlaneBytesIndependentlyCompared':len(water)+len(uncertain),
            'waterAndUncertaintyOverlapCells':sum((a&b).bit_count() for a,b in zip(water,uncertain)),
            'scope':'Exact derivation/software and binary/gzip/metadata storage proof for declared grid and accepted source. No geographic completeness/shoreline accuracy/land/fallback/connector/mask policy/routing/ETA/app qualification.'}
