"""Portable complete country estimated-cost audit and explicit fact-view proof."""
import json
import sys
from verify_tagged_timing_routing_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();control=stage('tagged-timing-country-controls',True);country=stage('tagged-timing-country-run',True)
    assert control['factRoster']==load(HERE/'tagged-timing-capture-raw-v1/report.json')['factRoster']
    assert country['status']=='complete_typed_tagged_timing_costs_and_independent_python_prices_passed' and country['operation']=='run'
    assert country['sourceCounts']==dict(ids=42993567,xy=85987134,anchors=5731903,flags=5731903,geometry=48163649,ways=4227238,arcs=9882872)
    assert country['changedEstimatedWayRows']==2046669 and country['pricing']==dict(arcsChecked=9882872,costsChanged=4674440,defaultArcsChecked=5208379,primitiveOccurrences=74823887,nativeBatches=152)
    assert country['allPhysicalArcDescriptorsAndOrderExact'] and country['allDirectionsDefaultsRolesAndFlagsExact'] and country['nodeFlagsChanged']==0
    assert country['everyOldAndNewMacroPricePythonAudited']==9882872 and country['derivedFactBytes']==457255423
    assert country['maximumProposedMacroMs']==8408485 and country['proposedCostOverflowArcs']==2
    assert not country['originalLegalSpeedSourceFactsModified'] and country['countryCostFactsBuilt'] and not country['runtimeGraphBuilt'] and not country['accuracyOrAppAccepted']
    assert country['sourcePbfReads']==country['sourceConstructorExecutions']==country['routingQueries']==country['providerRequests']==country['applicationDbReads']==0
    closed=load(HERE/'tagged-timing-country-run-closed-v1.json')
    assert len(country['factRoster'])==29 and sum(v['bytes'] for v in country['factRoster'].values())==457255423
    for name,pin in country['factRoster'].items():assert closed['roster'][name]['bytes']==pin['bytes'] and closed['roster'][name]['sha256']==pin['sha256']
    total=result['newUniqueClosedAllocationBytes']
    for prefix in ('tagged-timing-country-controls','tagged-timing-country-run'):total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==8857067520
    plan=load(HERE/'tagged-timing-fact-view-plan-v1.json');catalog=load(HERE/'tagged-timing-fact-views-v1.json')
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    assert plan['previousClosedRoots']==304 and plan['newClosedAllocationBytes']==total
    assert catalog['recipeSha256']==sha(HERE/'tagged-timing-fact-view-plan-v1.json')
    assert catalog['actualFactFilesReadOrCopiedOrLinked']==catalog['nativeProgramsExecuted']==0
    assert catalog['originalLegalSpeedCatalogSha256']==sha(REPO/catalog['originalLegalSpeedCatalog'])
    sys.path.insert(0,str(REPO/'scripts'))
    from coarse_osm_fact_view_v1 import compose
    legal=load(REPO/catalog['originalLegalSpeedCatalog'])
    for label,pair in plan['sourcePairs'].items():
        assert catalog['views'][label]==compose(load(REPO/pair['base']),load(REPO/pair['overlay']))
        for name,pin in catalog['views'][label]['files'].items():
            if not name.rsplit('/',1)[-1].startswith(('ways-','arcs-')):
                old=legal['views'][label]['files'][name];assert pin['bytes']==old['bytes'] and pin['sha256']==old['sha256']
    return {**result,'status':'complete_country_tagged_estimated_costs_and_separate_legal_source_views_passed',
            'all9882872OldAndProposedCountryPricesIndependentlyAudited':True,'allCountryPhysicalDescriptorsAndNodeFlagsPreserved':True,
            'estimatedCostFactsBytes':457255423,'originalLegalSpeedFactsPreserved':True,
            'uniqueClosedRoots':304,'newUniqueClosedAllocationBytes':total,'timingCountryRuntimeGraphBuilt':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
