"""Portable completed source-cost lineage/overlay proof; never replay producers."""
import json
import sys

from verify_entry_runtime_v1 import stage
from verify_explicit_lane_source_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();total=result['newUniqueClosedAllocationBytes']
    prefixes=('explicit-lane-overlay-controls','explicit-lane-overlay-capture','explicit-lane-overlay-country-controls',
              'explicit-lane-overlay-country-run','explicit-lane-flag-lineage','explicit-lane-overlay-v2-controls',
              'explicit-lane-overlay-v2-country-controls','explicit-lane-overlay-v2-country-run')
    first=stage(prefixes[0],True);assert first['controls']=={'tests':15,'successful':True,'failures':0,'errors':0,'skips':0}
    captured=stage(prefixes[1],True)
    assert (captured['originalWaysChecked'],captured['originalFlagsChecked'],captured['originalArcsChecked'])==(28995,46881,79118)
    assert captured['changedWayRows']==28 and captured['addedNativePricedArcs']==30
    assert captured['physicalPackedFieldsByteIdentical']==11 and captured['paidFixturesExact']==82
    assert captured['singleViaContextRulesExact']==295 and captured['remainingClosedWaysExact']==506
    assert captured['queriesExecutedHere']==0 and captured['qualifiedFiniteResultsReusedByIdentity']==81 and captured['qualifiedUnavailableResultsReusedByIdentity']==1
    control=stage(prefixes[2],True)
    assert control['operation']=='controls' and control['factRoster']==captured['factRoster']
    assert control['newNativePricedArcsIndependentlyRebuilt']==30 and control['allOldSourceRowsAndArcCostsExact']
    stopped=load(HERE/'explicit-lane-overlay-country-run-closed-v1.json')
    root=HERE/'explicit-lane-overlay-country-run-raw-v1'
    assert stopped['terminalRecord']=='failure.json' and not any(n.startswith('cost-facts/') for n in stopped['roster'])
    for name,pin in stopped['roster'].items():
        if not pin['ignoredLargeAsset']:assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    plan=load(root/'execution-plan.json')
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    assert 'Only original lane exclusions can reopen' in load(root/'failure.json')['error']
    assert load(root/'run-summary.json')['exitCode']==2
    failed=load(root/'container-result.json')
    assert failed['State']['ExitCode']==failed['clientExitCode']==2 and not failed['State']['OOMKilled']
    assert load(root/'cleanup.json')['removed'] and load(root/'cleanup.json')['independentInspectAbsent']
    review=stage(prefixes[4])
    assert review['wayRowsVisited']==4227238 and review['selectedWaysChecked']==3292
    assert review['storedFlagsMatchOriginalSourcePolicy'] and review['storedFlagsDifferFromCurrentRejectedPolicy']==3
    assert review['counts']=={'original/lane-access':3289,'current/lane-access':3292,'original/conditional-or-way-restriction':3}
    for row in review['mismatches']:
        assert row['storedFlags']==row['expectedOriginalFlags'] and row['storedFlags']>>8==5
        assert row['expectedCurrentFlags']>>8==6 and row['currentPolicy']['reason']=='lane-access'
        assert row['originalPolicy']['reason']=='conditional-or-way-restriction' and row['proposedPolicy']['reason'] is None
    assert review['sourceRowsModified']==review['coordinateReads']==review['sourcePbfReads']==0
    second=stage(prefixes[5],True);assert second['controls']=={'tests':17,'successful':True,'failures':0,'errors':0,'skips':0}
    v2control=stage(prefixes[6],True)
    assert v2control['status']=='complete_explicit_lane_source_fact_overlay_v2_passed'
    assert v2control['operation']=='controls' and v2control['factRoster']==control['factRoster']
    country=stage(prefixes[7],True)
    assert country['status']=='complete_explicit_lane_source_fact_overlay_v2_passed' and country['operation']=='run'
    assert country['sourceCounts']=={'ids':42993567,'xy':85987134,'anchors':5731903,'flags':5731903,'geometry':48163649,'ways':4227238,'arcs':9878318}
    assert country['overlayCounts']=={'records':3292,'changedGraphWays':3292,'newPreClosureArcs':4554,'sourcePolicyLabelRetainedFromEarlierVersion':3}
    assert country['resultWays']==4227238 and country['resultFlags']==5731903 and country['resultPreClosureArcs']==9882872
    assert country['allOldSourceRowsAndArcCostsExact'] and country['newNativePricedArcsIndependentlyRebuilt']==4554
    assert country['nodeFlagsChanged']==0 and not country['sourceRestrictionFactsChanged']
    assert country['overlayBytes']==457255423 and country['newPreClosureCostOverflows']==0
    assert country['sourcePbfReads']==country['sourceConstructorExecutions']==country['routingQueries']==country['providerRequests']==country['applicationDbReads']==0
    assert country['nationalFactOverlayBuilt'] and not country['runtimeGraphBuilt'] and not country['etaOrAppAccepted']
    closed=load(HERE/'explicit-lane-overlay-v2-country-run-closed-v1.json')
    assert sum(p['bytes'] for p in country['factRoster'].values())==457255423 and len(country['factRoster'])==29
    for name,pin in country['factRoster'].items():
        assert closed['roster'][name]['bytes']==pin['bytes'] and closed['roster'][name]['sha256']==pin['sha256']
    initial=load(HERE/'explicit-lane-overlay-v2-country-run-raw-v1/container-initial.json')['HostConfig']
    assert initial['NetworkMode']=='none' and initial['ReadonlyRootfs'] and initial['NanoCpus']==2000000000 and initial['PidsLimit']==64
    for prefix in prefixes:total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==7884292096 and 64500000000+total+104857600+805306368+268435456<72*1024**3
    factory=load(HERE/'explicit-lane-fact-view-plan-v1.json')
    assert factory['controls']==13 and factory['previousClosedRoots']==277 and factory['newClosedAllocationBytes']==total
    assert sha(HERE/'explicit-lane-fact-view-plan-v1.json')=='4123167c014063b525da01e8740d92d0bedae4204a3dbf9c7ff0c56e0a11e1cb'
    for name,pin in factory['bindings'].items():assert sha(REPO/name)==pin,name
    catalog=load(HERE/'explicit-lane-fact-views-v1.json')
    assert catalog['recipeSha256']==sha(HERE/'explicit-lane-fact-view-plan-v1.json')
    assert catalog['actualFactFilesReadOrCopiedOrLinked']==catalog['nativeProgramsExecuted']==0
    sys.path.insert(0,str(REPO/'scripts'))
    from coarse_osm_fact_view_v1 import compose
    for label,pair in factory['sourcePairs'].items():
        assert catalog['views'][label]==compose(load(REPO/pair['base']),load(REPO/pair['overlay']))
    assert catalog['views']['country']['fields']['arcs']['bytes']==9882872*32
    return {**result,'status':'completed_national_lane_source_overlay_v2_and_lineage_proof_passed',
            'failedNationalV1EvidencePreserved':True,'all3292OriginalWayFlagsReviewed':True,
            'laneNativeOverlayV2LinuxControls':17,'nationalAddedPreClosureArcsSourceAudited':4554,
            'nationalLaneFactBytesSourceAudited':457255423,'newCompleteFactViewsVerified':True,
            'uniqueClosedRoots':277,'newUniqueClosedAllocationBytes':total,'laneNationalGraphBuilt':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
