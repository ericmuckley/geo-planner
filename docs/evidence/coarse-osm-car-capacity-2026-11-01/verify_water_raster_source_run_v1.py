"""Portable complete compact country raster, no geography policy or app admission."""
import json
from verify_water_raster_source_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();report=stage('water-raster-source-run',True)
    assert report['status']=='national_compact_water_raster_derivative_and_binary_audit_complete'
    raster=report['raster'];stats=raster['statistics'];manifest=raster['manifest'];planes=manifest['planes']
    assert (stats['features'],stats['rings'],stats['points'])==(2439095,2648285,102511022)
    assert stats['excludedBoxes']==594 and stats['incompleteBoxes']==1 and stats['maxFeatureCrossings']==7942
    assert stats['planeBytes']==stats['nativeBackingBytes']==raster['allCompressedAndRawPlaneBytesIndependentlyCompared']==15340000
    assert stats['finished']==1 and stats['failed']==stats['activeFeature']==0
    assert manifest['grid']=={'xE7':-1250000000,'yE7':240000000,'stepE7':50000,'columns':11800,'rows':5200,'cells':61360000,'bitOrder':'row-major-lsb-first'}
    assert planes['water']['compressedBytes']==445308 and planes['water']['setCells']==995924
    assert planes['uncertainty']['compressedBytes']==1336191 and planes['uncertainty']['setCells']==8316641
    assert planes['water']['rawSha256']=='111cec674ec0165e81812637c6072c826f97433fba3445a205b4ac60c2197b7e'
    assert planes['uncertainty']['rawSha256']=='04d04a3be26668749ace05f7342840fc9243c4255b417925f3d013f54ee529c8'
    assert raster['waterAndUncertaintyOverlapCells']==794770
    assert raster['manifestSha256']=='048b2ce763a80e75c9fbe651acf5ef43dfe91515f99276357ea7357bbd2c809e'
    assert not manifest['sourceGeometryCompletelyBounded'] and len(manifest['sourceIncompleteFeatures'])==1
    assert report['producerNativeArraysReleased'] and not report['sourcePbfReads'] and not report['modelQueries'] and not report['providerRequests'] and not report['maskOrModelChanged'] and not report['appActivated']
    return {**result,'waterCountryCompactRasterCompleted':True,'waterCompactCompressedPlaneBytes':1781499,
            'waterCompactDecodedPlaneBytes':15340000,'newUniqueClosedAllocationBytes':5320548352,'uniqueClosedRoots':151,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
