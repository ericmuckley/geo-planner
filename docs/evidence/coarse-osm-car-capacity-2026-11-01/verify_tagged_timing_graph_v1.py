"""Portable derived-cost graph audit and exact unchanged physical wire proof."""
import json
from verify_tagged_timing_country_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous()
    assert stage('tagged-timing-graph-controls',True)['controls']==dict(tests=38,successful=True,failures=0,errors=0,skips=0)
    report=stage('tagged-timing-graph-run',True);audit=report['independentAudit']
    assert report['status']=='tagged_timing_national_graph_and_independent_complete_audit_passed'
    assert report['augmentationCounts']==[25398,235258,24947,451,258059,9826630]
    assert audit['allPreArcMappingsChecked']==9882872 and audit['finalForbiddenPairsChecked']==258059
    assert audit['baseFields']['directedCostsAndPhysicalReversesChecked']==9826630 and audit['baseFields']['sourceTurnRecordsChecked']==409178
    assert report['finalPayloadBytes']==129290987 and report['routingQueries']==0 and not report['appActivated']
    old=load(HERE/'lane-graph-run-raw-v1/artifacts.json');new=load(HERE/'tagged-timing-graph-run-raw-v1/artifacts.json')
    assert old.keys()==new.keys();same=[]
    for name,pin in new.items():
        if name.rsplit('/',1)[-1] in ('costs.u16','cost-overflow-arcs.u24','cost-overflow-ticks.u32'):continue
        assert (pin['bytes'],pin['sha256'])==(old[name]['bytes'],old[name]['sha256']);same.append(name)
    assert len(same)==8
    total=result['newUniqueClosedAllocationBytes']
    for prefix in ('tagged-timing-graph-controls','tagged-timing-graph-run'):total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==8990605312
    return {**result,'status':'derived_timing_national_graph_source_audited_physical_wire_exact',
            'timingCountryRuntimeGraphBuilt':True,'eightNoncostCsrFieldsByteIdenticalToLegalSpeedGraph':True,
            'uniqueClosedRoots':306,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
