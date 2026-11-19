"""Portable new read-only fact view/entry preservation controls and stops."""
import json
from verify_conditional_country_overlay_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def stopped(prefix,error):
    record=load(HERE/(prefix+'-closed-v1.json'));root=HERE/(prefix+'-raw-v1')
    for name,pin in record['roster'].items():
        if not pin['ignoredLargeAsset']:assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    for name,pin in load(root/'execution-plan.json')['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    assert record['terminalRecord']=='failure.json' and error in load(root/'failure.json')['error']
    assert load(root/'cleanup.json')['independentInspectAbsent'] and load(root/'run-summary.json')['exitCode']==2
    final=load(root/'container-result.json');assert final['State']['ExitCode']==final['clientExitCode']==1 and not final['State']['OOMKilled']
    return record['usage']['conservativeAllocatedBytes']


def verify():
    result=previous();total=result['newUniqueClosedAllocationBytes']
    plan=load(HERE/'conditional-fact-view-plan-v1.json');catalog=load(HERE/'conditional-fact-views-v1.json')
    assert catalog['recipeSha256']==sha(HERE/'conditional-fact-view-plan-v1.json')
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    assert catalog['actualFactFilesReadOrCopiedOrLinked']==catalog['nativeProgramsExecuted']==0
    assert len(catalog['views']['captured']['files'])==9 and len(catalog['views']['country']['files'])==88
    assert catalog['views']['country']['fields']['arcs']['bytes']==9878318*32
    total+=stopped('conditional-entry-resolution-controls','coarse_osm_car_packed_native_v1')
    total+=stopped('conditional-entry-resolution-v2-controls',"KeyError('artifact')")
    report=stage('conditional-entry-resolution-v3-controls',True)
    assert report['controls']=={'tests':37,'successful':True,'failures':0,'errors':0,'skips':0}
    assert report['countryFactReads']==report['sourcePbfReads']==0
    total+=load(HERE/'conditional-entry-resolution-v3-controls-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==5898633216
    return {**result,'conditionalFactViewCatalogOnly':True,'conditionalEntryViewAndNativeControls':37,
            'conditionalEntryTwoPretestStopsPreserved':True,'uniqueClosedRoots':186,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
