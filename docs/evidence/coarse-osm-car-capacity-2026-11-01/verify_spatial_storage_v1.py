"""Portable lossless spatial output/query proof; no ignored asset reads."""
import json
from verify_preparation_v1 import HERE, REPO, closed, load, sha


def host_closed(prefix,version='v1'):
    record=load(HERE/f'{prefix}-closed-{version}.json');root=HERE/f'{prefix}-raw-{version}'
    for name,pin in record['roster'].items():
        if pin['ignoredLargeAsset']:continue
        path=root/name;assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256'],name
    plan=load(root/'execution-plan.json')
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    assert record.get('terminalRecord','report.json')=='report.json'
    return root


def verify():
    root,_=closed('spatial-native','build','v1',0)
    result=load(root/'result.json');assert result['artifactBytes']==2069704 and result['artifactSha256']=='b9fd93c3cbd44115b810a13a8f43040d1c11b41f7edce9a2ddb1f8afc41683b1'
    root,_=closed('spatial-native','controls','v1',2)
    assert load(root/'worker-failure.json')['errorType']=='ImportError' and 'NativePacked' in load(root/'worker-failure.json')['error']
    root,_=closed('spatial-native','controls','v2',0)
    assert load(root/'controls.json')=={'tests':11,'successful':True,'failures':0,'errors':0,'skips':0}
    root,_=closed('spatial-native','equivalence','v2',0);result=load(root/'result.json')
    assert result['filesIndependentlyCompared']==15 and result['originalDirectionalFixturesMapped']==82
    fixtures=load(root/'query-fixtures.json')
    plan=load(HERE/'spatial-search-runtime-plan-v1.json')
    for field in ('codeBindings','evidenceBindings'):
        for name,pin in plan[field].items():assert sha(REPO/name)==pin,name
    runtime=load(HERE/'spatial-search-runtime-v1.json')
    assert runtime['recipeSha256']==sha(HERE/'spatial-search-runtime-plan-v1.json')
    assert runtime['originalDirectionalCases']==82 and runtime['unreachableCasesPreserved']==14 and runtime['paidPartialEndpointsChecked']==20
    assert [c['ticks'] for c in runtime['checks']]==[c['expectedTicks'] for c in fixtures]
    root,_=closed('spatial-country','controls','v1',0)
    assert load(root/'controls.json')=={'tests':10,'successful':True,'failures':0,'errors':0,'skips':0}
    root,_=closed('spatial-country','run','v1',0);result=load(root/'result.json')
    assert (result['vertices'],result['arcs'],result['forbiddenTurnPairs'])==(5731903,9620680,224675)
    assert (result['routingPayloadBytes'],result['spatialCells'],result['spatialIndexBytes'],result['totalBytesIncludingOfflinePermutations'])==(127854983,56970,341823,189607138)
    assert not result['arbitraryOriginSnappingBuilt'] and not result['etaQualified'] and not result['vercelQualified']
    root,_=closed('spatial-country','audit','v1',0);audit=load(root/'result.json')
    assert audit['status']=='independent_complete_lossless_spatial_permutation_audit_passed'
    assert (audit['verticesChecked'],audit['directedArcsCostsPhysicalReversesChecked'],audit['forbiddenTurnPairsChecked'],audit['spatialCellsChecked'])==(5731903,9620680,224675,56970)
    assert audit['nativeLibraryExecutions']==audit['sourcePbfReads']==audit['sourceConstructorExecutions']==0
    profile=load(host_closed('spatial-country-profile')/'report.json')
    assert profile['routingAndSpatialCompressedBytes']==83090627 and profile['retainedDataBackingBufferBytes']==129399391
    original=load(HERE/'packed-country-profile-raw-v2/report.json')
    assert [case['ticks'] for case in profile['queries']]==[case['ticks'] for case in original['queries']]==[296763,256312,None,None]
    return {'allNationalVerticesAndArcsLosslesslyVerified':True,'originalCapturedQueriesPreserved':82,
            'spatialCells':56970,'spatialIndexBytes':341823,'plainGzipBytes':83090627,
            'appOrSnapQualified':False,'reads':'Small mirrored records and bound code only.'}


if __name__=='__main__':print(json.dumps(verify()))
