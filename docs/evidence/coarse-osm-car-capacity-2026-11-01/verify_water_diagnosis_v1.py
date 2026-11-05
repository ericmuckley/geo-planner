"""Portable all83 path/shading/source-exposure diagnosis; never replay a producer."""
import json
from collections import Counter
from verify_water_candidate_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();controls=load(HERE/'water-path-controls-v1.json')
    assert controls['tests']==43 and controls['failures']==0 and controls['strictTypesPassed'] and controls['reviewPythonTests']==2
    assert sha(HERE/controls['log'])==controls['logSha256']
    for name,pin in controls['bindings'].items():assert sha(REPO/name)==pin,name
    paths=stage('water-paths');candidate=load(HERE/'water-country-evaluation-raw-v1/report.json')
    assert paths['status']=='frozen_water_candidate_path_diagnostic_complete' and paths['paths']==paths['newRoadSearches']==83
    assert paths['reusedRoadPaths']==paths['unavailable']==paths['providerRequests']==0 and not paths['candidateAdmitted']
    assert len(paths['rows'])==83 and len(paths['phases'])==21
    assert Counter(row['kind'] for row in paths['rows'])=={'road-foot':61,'local-grid':22}
    timings={key:row for phase in candidate['phases'] for key,row in phase['diagnostic']['timings'].items()}
    assert {row['id'] for row in paths['rows']}==set(timings)
    for row in paths['rows']:assert sum(row['components'].values())==row['sumTicks']==timings[row['id']]['ticks']
    outputs={tuple(p['origin']):p['diagnostic']['output']['sha256'] for p in candidate['phases']}
    for phase in paths['phases']:assert phase['outputSha256']==outputs[tuple(phase['origin'])]
    assert paths['afterLoad']['arrayBuffers']==paths['afterQueries']['arrayBuffers']==157207750
    offline=max(row['searchStats']['offlineSearchBackingBytes'] for row in paths['rows'])
    trace=max(phase['traceStats']['maximumBackingBufferBytes'] for phase in paths['phases'])
    assert offline==85630800 and trace==94257215 and trace<134217728
    shading=stage('water-shading')
    assert shading['status']=='all83_saved_public_shading_and_mask_cells_audited'
    assert len(shading['rows'])==shading['pointsOnMask']==83 and len(shading['maps'])==37
    assert shading['baselineArrayBuffers']==shading['releasedArrayBuffers']==74986
    assert shading['roadQueries']==shading['newDisplays']==shading['sourcePbfReads']==shading['providerRequests']==0
    mismatches=[row for row in shading['rows'] if row['pointOnMask'] and row['centerOnMask'] is False]
    assert len(mismatches)==1 and mismatches[0]['budgetMinutes']==720 and mismatches[0]['pointMinutes']==74
    assert not mismatches[0]['shaded'] and mismatches[0]['primaryPaidSegmentAllowed']
    assert not mismatches[0]['pointObservation']['sourceUncertainty'] and mismatches[0]['centerObservation']['sourceUncertainty']
    plan=load(HERE/'water-path-findings-plan-v1.json');findings=load(REPO/plan['output'])
    assert sha(HERE/'water-path-findings-plan-v1.json')==findings['recipeSha256']
    for name,pin in plan['bindings'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    assert len(findings['rows'])==83 and not findings['unavailable']
    assert findings['providerRequests']==findings['modelQueries']==0 and not findings['policyChanged']
    assert abs(findings['overall']['meanAbsoluteErrorMinutes']-32.614352409638556)<1e-10
    assert findings['sourceSpeedAttributeUniqueKnownArcs']==44475 and findings['sourceSpeedAttributeUniqueUnknownArcs']==244
    assert findings['sourceSpeedTickTotals']=={'explicitTicks':13064365,'defaultTicks':1812251,'unknownTicks':88807}
    for row in findings['rows']:
        exposure=row['sourceSpeedExposure'];assert sum(exposure[key] for key in ['explicitTicks','defaultTicks','unknownTicks'])==row['components']['roadTravelTicks']
    total=result['newUniqueClosedAllocationBytes']+sum(load(HERE/f'{name}-closed-v1.json')['usage']['conservativeAllocatedBytes'] for name in ['water-shading','water-paths'])
    assert total==5381672960
    return {**result,'waterCandidatePathSumsChecked':83,'waterCandidateDiagnosticOutputShasChecked':21,
            'waterCandidatePathUnavailable':0,'waterOfflineWitnessSearchBackingBytes':offline,
            'waterOfflineTraceBackingBytes':trace,'waterSavedPublicShadingCasesChecked':83,
            'waterKnownDryPointCoarseCellOmissions':1,'waterKnownSourceAttributeArcs':44475,
            'waterUnknownSourceAttributeArcs':244,'newUniqueClosedAllocationBytes':total,
            'uniqueClosedRoots':166,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
