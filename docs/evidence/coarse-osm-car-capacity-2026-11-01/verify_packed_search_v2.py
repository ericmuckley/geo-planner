"""Portable packed candidate/native equivalence and complete captured query proof."""
import json
from verify_preparation_v1 import HERE, REPO, closed, load, sha


def verify():
    root,_=closed('packed-capture','run','v1',0)
    report=load(root/'report.json')
    assert (report['vertices'],report['arcs'],report['forbiddenTurnPairs'],report['payloadBytes'])==(46881,75137,2282,1027089)
    assert report['nativePointsRetainedOffline']==143560 and report['paidInternalAliases']==96679
    assert load(root/'controls.json')=={'tests':5,'successful':True,'failures':0,'errors':0,'skips':0}
    fixtures=load(root/'query-fixtures.json');assert len(fixtures)==82
    plan=load(HERE/'packed-search-runtime-plan-v2.json')
    for field in ('codeBindings','evidenceBindings'):
        for name,pin in plan[field].items():assert sha(REPO/name)==pin,name
    runtime=load(HERE/'packed-search-runtime-v2.json')
    assert runtime['recipeSha256']==sha(HERE/'packed-search-runtime-plan-v2.json')
    assert runtime['status']=='all_original_captured_packed_search_queries_exact'
    assert runtime['originalDirectionalCases']==82 and runtime['unreachableCasesPreserved']==14 and runtime['paidPartialEndpointsChecked']==20
    assert runtime['wireBytes']==1027089 and runtime['retainedBackingBufferBytes']==1036482 and runtime['maxSearchBufferBytes']==8300548
    assert [case['ticks'] for case in runtime['checks']]==[case['expectedTicks'] for case in fixtures]
    assert load(HERE/'packed-search-host-controls-v1.json')['generatedIndependentSearchComparisons']==2560
    for stage in ('build','controls','equivalence'):
        root,_=closed('packed-native',stage,'v1',0)
        result=load(root/'result.json')
        if stage=='build':assert result['artifactSha256']=='0c740c965b781dcc405365ac877dd1963ad1991b2ca436df04c6ac8107e838e9' and result['artifactBytes']==2065752
        if stage=='controls':assert load(root/'controls.json')=={'tests':8,'successful':True,'failures':0,'errors':0,'skips':0}
        if stage=='equivalence':assert result['filesByteIdentical']==11 and result['bytesIndependentlyCompared']==1027089
    return {'packedReaderSearchHostControls':14,'independentGeneratedQueries':2560,'allOriginalRealRoadQueriesExact':82,
            'unreachablePreserved':14,'paidPartialEndpointsChecked':20,'nativeLinuxControls':8,'allNativeWireBytesIndependentlyCompared':1027089,
            'nationalOrAppQualified':False,'reads':'Small mirrored records and bound repository code only; no graph/PBF/native/worker/provider/application DB.'}


if __name__=='__main__':print(json.dumps(verify()))
