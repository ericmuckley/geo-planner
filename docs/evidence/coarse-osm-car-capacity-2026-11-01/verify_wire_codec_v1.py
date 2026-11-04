"""Portable full-byte codec audit and fresh host loader/query proof."""
import json
from verify_preparation_v1 import HERE, REPO, closed, load, sha
from verify_spatial_storage_v1 import host_closed, verify as spatial


def verify():
    spatial()
    root=host_closed('wire-codec');report=load(root/'report.json');manifest=load(root/'manifest.json')
    assert report['fields']==len(manifest['fields'])==13 and report['rawBytes']==128196806 and report['compressedBytes']==45859429
    original=load(HERE/'spatial-country-closed-run-v1.json')['roster']
    for name,row in manifest['fields'].items():assert row['rawBytes']==original[name]['bytes'] and row['rawSha256']==original[name]['sha256'],name
    independent=load(HERE/'wire-codec-independent-plan-v1.json')
    for name,pin in independent['codeBindings'].items():assert sha(REPO/name)==pin,name
    root,_=closed('wire-codec','audit','v1',0)
    assert load(root/'controls.json')=={'tests':8,'successful':True,'failures':0,'errors':0,'skips':0}
    audit=load(root/'audit.json')
    assert audit['status']=='independent_complete_storage_codec_all_bytes_passed'
    assert audit['fields']==13 and audit['bytesIndependentlyDecodedAndCompared']==128196806 and audit['compressedBytes']==45859429
    assert audit['sourcePbfReads']==audit['sourceConstructorExecutions']==audit['nativeLibraryExecutions']==0
    root=host_closed('wire-codec-profile');profile=load(root/'report.json')
    assert profile['status']=='host_compressed_national_loader_and_original_queries_passed'
    assert profile['decodedWireBytes']==128196806 and profile['compressedBytes']==45859429 and profile['retainedDataBackingBufferBytes']==129399391
    assert profile['hostFirstLoadAndQueryMsIncludingGc']<5000
    assert [case['ticks'] for case in profile['queries']]==[296763,256312,None,None]
    assert all(case['searchBufferBytes']==46482720 for case in profile['queries'])
    assert not profile['modelChanged']
    return {'everyOriginalWireByteIndependentlyDecoded':128196806,'compressedCoreAndIndexBytes':45859429,
            'retainedDataBackingBufferBytes':129399391,'originalNationalQueriesPreserved':4,
            'hostCoreFirstLoadAndQueryMs':profile['hostFirstLoadAndQueryMsIncludingGc'],
            'arbitraryOriginOrFullAppOrEtaQualified':False,
            'reads':'Small mirrored records and bound repository code only; no graph/source/worker/native/provider/application DB.'}


if __name__=='__main__':print(json.dumps(verify()))
