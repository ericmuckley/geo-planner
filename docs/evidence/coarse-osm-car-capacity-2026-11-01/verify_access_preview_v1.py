"""Portable rejected-candidate/local-review proof, without rendering or model replay."""
import json
from verify_preparation_v1 import HERE,REPO,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_access_candidate_v1 import verify as candidate


def verify():
    result=candidate();root=host_closed('access-preview');report=load(root/'report.json');review=load(root/'browser-review.json')
    assert report['status']=='offline_three_case_same_camera_preview_prepared' and len(report['cases'])==3
    assert [case['budgetMinutes'] for case in report['cases']]==[360]*3
    assert [case['stepDegrees'] for case in report['cases']]==[0.005,0.007234,0.006256]
    closed=load(HERE/'access-preview-closed-v1.json');assert closed['roster']['index.html']['sha256']==report['htmlSha256'] and closed['roster']['index.html']['bytes']==report['htmlBytes']
    assert review['status']=='local_comparison_verified_in_chrome' and review['pageOriginConsoleErrors']==0
    assert review['unrelatedExtensionErrors']==1 and not review['responsiveViewportOverrideUsed']
    assert review['closingWrapperSha256']==sha(REPO/'scripts/close_osm_access_preview_host_v1.py')
    assert len(review['screenshots'])==3
    for name,pin in review['screenshots'].items():assert pin['sha256']==closed['roster'][name]['sha256'] and pin['bytes']==closed['roster'][name]['bytes']
    return {**result,'localSameCameraReviewCases':3,'pageOriginConsoleErrors':0,'newUniqueClosedAllocationBytes':2344247296+closed['usage']['conservativeAllocatedBytes'],
            'productionOrExperimentalAppActivated':False,'reads':'Small bound code/mirrored records only; no model/output/preview render, browser/provider/DB.'}


if __name__=='__main__':print(json.dumps(verify()))
