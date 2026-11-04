"""Portable completed exact national water-reference/index audit and format oracle."""
import json
from verify_water_source_gap_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();report=stage('water-references-source-run',True)
    assert report['status']=='national_water_exact_references_and_unique_ids_audited'
    assert report['producerBuffersReleasedBeforeAudit']
    receipt=load(HERE/'water-references-source-run-raw-v1/receipt.json')
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames']==0
    assert receipt['counts']=={'node':1606229364,'way':162688797,'relation':1624265}
    assert receipt['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    prior=load(HERE/'water-union-source-run-raw-v1/report.json')['water'];water=report['water']
    assert {k:water[k] for k in prior}==prior
    capture=water['referenceCapture'];store=water['referenceStore'];audit=report['independentAudit']
    assert capture['ways']==audit['allWayRecordsAndFieldsDecoded']==2829193
    assert capture['references']==audit['allReferenceOccurrencesChecked']==104806243
    assert capture['uniqueNodes']==store['uniqueNodes']==audit['allUniqueNodeIdsIndependentlyCompared']==101738006
    assert capture['rawGpfBytes']==store['ways']['rawBytes']==audit['allSavedGpfBytesChecked']==1209111100
    assert store['nodes']['rawBytes']==audit['allRawIdBytesCompared']==813904048
    assert store['ways']['rawSha256']=='44602922a9f5fa953c47572b93b5db8e1a29d9710c381f3b14fe8f10de133f20'
    assert store['nodes']['rawSha256']=='587da8a37ae28bfaae38709faf3f016cc03383b61dfef56e06d8be8428c988fd'
    assert store['compressedBytes']==store['ways']['compressedBytes']+store['nodes']['compressedBytes']==414499840
    assert all(sum(p['bytes'] for p in store[k]['parts'])==store[k]['compressedBytes'] and
               sum(p['rawBytes'] for p in store[k]['parts'])==store[k]['rawBytes'] for k in ('ways','nodes'))
    assert not store['coordinatesRetained'] and not report['coordinatesOrGeometryRetained']
    prototype=load(HERE/'water-coordinate-format-v1.json')
    assert prototype['qualification']['tests']==7 and prototype['qualification']['successful']
    assert not prototype['nativePerformanceNationalCoverageOrAppAdmission']
    for name,pin in prototype['bindings'].items():assert sha(REPO/name)==pin
    return {**result,'waterNationalExactReferenceCaptureCompleted':True,'waterUniqueReferencedNodes':101738006,
            'waterReferenceCompressedBytes':414499840,'waterCoordinateFormatHostControls':7,
            'newUniqueClosedAllocationBytes':3341860864,'uniqueClosedRoots':128,
            'waterNationalCoordinateCaptureCompleted':False,'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
