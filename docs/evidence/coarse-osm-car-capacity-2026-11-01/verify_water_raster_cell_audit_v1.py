"""Portable independent raw source/cell audit, no national mask accuracy claim."""
import json
from verify_water_raster_reader_v1 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();controls=stage('water-raster-cell-audit-controls',True)
    assert controls['controls']=={'tests':12,'successful':True,'failures':0,'errors':0,'skips':0}
    report=stage('water-raster-cell-audit-run',True)
    assert report['status']=='independent_raw_water_center_and_closed_cell_packet_audit_complete'
    assert report['allRawCenterCounts']==report['allRawBoundaryCounts']==[2439095,2648285,102511022]
    assert len(report['comparisons'])==512 and report['mismatchIndices']==[]
    assert sum(r['phase']=='saved-cell-center' for r in report['comparisons'])==245
    assert all(r['waterMatches'] and r['uncertaintyMatches'] for r in report['comparisons'])
    assert len(report['unboundedSourceFeaturesRetained'])==1
    assert not report['sourcePbfReads'] and not report['modelQueries'] and not report['providerRequests'] and not report['maskOrModelChanged'] and not report['appActivated']
    return {**result,'waterRawSourceCellComparisonsPassed':512,'newUniqueClosedAllocationBytes':5325303808,'uniqueClosedRoots':154,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
