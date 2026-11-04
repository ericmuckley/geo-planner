"""Portable completed field proof preserving both verifier lifetime stops."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_origin_connections_v1 import verify as origins


def failed(version,fragment):
    record=load(HERE/f'road-field-profile-closed-{version}.json');root=HERE/f'road-field-profile-raw-{version}'
    assert record['terminalRecord']=='failure.json'
    for name,pin in record['roster'].items():
        if pin['ignoredLargeAsset']:continue
        assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    plan=load(root/'execution-plan.json')
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    failure=load(root/'failure.json');assert fragment in failure['error']
    return failure


def verify():
    origins()
    failed('v1','No retained field backing buffers between phases')
    second=failed('v2','after reference pair phase: retained backing buffers')
    assert 'baseline=141003652, observed=187486372' in second['error']
    controls=load(HERE/'road-field-controls-v1.json')
    for name,pin in controls['codeBindings'].items():assert sha(REPO/name)==pin,name
    assert controls['tests']==11 and controls['successful'] and controls['failures']==controls['skips']==0
    assert controls['qualifiedPairSearchGeneratedPositionComparisons']==3000
    assert controls['consoleSha256']==sha(HERE/'road-field-controls-v1.txt') and controls['designSha256']==sha(HERE/'road-field-design-v1.json')
    lifetime=load(HERE/'road-field-lifetime-controls-v3.json')
    for name,pin in lifetime['codeBindings'].items():assert sha(REPO/name)==pin,name
    assert lifetime['tests']==4 and lifetime['successful'] and lifetime['extraBufferGuardBytes']==1048576 and lifetime['deliberateRetainedBufferRefusalPassed']
    assert lifetime['consoleSha256']==sha(HERE/'road-field-lifetime-controls-v3.txt')
    root=host_closed('road-field-profile','v3');report=load(root/'report.json');plan=load(root/'execution-plan.json')
    assert report['status']=='host_national_fields_and_qualified_pair_comparisons_passed'
    assert report['fields']==len(report['rows'])==32 and report['originalRequestPairSoftwareComparisons']==48
    assert report['maximumFieldBackingBufferBytes']==57946526<67108864
    baseline=report['retainedAfterLoad']['arrayBuffers'];comparisons=[]
    for row in report['rows']:
        assert row['stats']['maximumBackingBufferBytes']==57946526 and row['stats']['returnedBackingBufferBytes']==49946526
        assert row['afterFieldRelease']['arrayBuffers']<=baseline+1048576 and row['afterPairRelease']['arrayBuffers']<=baseline+1048576
        comparisons.extend(row['comparisons'])
        for case in row['comparisons']:
            if case['pairTotalTicks'] is None:assert case['fieldTotalUpper'] is None or case['fieldTotalUpper']>row['minutes']*480
            else:assert case['pairTotalTicks']<=case['fieldTotalUpper']<=case['pairTotalTicks']+7
    assert len(comparisons)==48 and sum(case['pairTotalTicks'] is not None for case in comparisons)==19
    assert sorted(row['minutes'] for row in report['rows'])==sorted(plan['horizonsMinutes']*8)
    assert report['afterQueries']['arrayBuffers']<=baseline+1048576 and not report['modelChanged']
    ranges={str(minutes):[min(row['fieldMsIncludingAllocationAndSearch'] for row in report['rows'] if row['minutes']==minutes),max(row['fieldMsIncludingAllocationAndSearch'] for row in report['rows'] if row['minutes']==minutes)] for minutes in plan['horizonsMinutes']}
    return {'fields':32,'pairSoftwareComparisons':48,'finiteAtThoseBudgets':19,'nullAtThoseBudgetsRetained':29,
            'maximumFieldBackingBufferBytes':57946526,'fieldAllocationAndSearchMsRanges':ranges,
            'hostLoadConnectionAndFirstFieldMsIncludingGc':report['hostFirstLoadConnectionAndFieldMsIncludingGc'],
            'preservedLifetimeVerifierStops':2,'filledDisplayOrEtaOrAppQualified':False,
            'reads':'Small mirrored records and bound code only; no large graph/source/native/Docker/provider/DB.'}


if __name__=='__main__':print(json.dumps(verify()))
