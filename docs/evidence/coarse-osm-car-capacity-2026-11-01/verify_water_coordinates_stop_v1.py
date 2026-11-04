"""Portable stopped coordinate run; preserve its incomplete data and limits."""
import json
from verify_water_coordinates_controls_v1 import verify as previous
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();record=load(HERE/'water-coordinates-source-run-closed-v1.json');root=HERE/'water-coordinates-source-run-raw-v1'
    for name,pin in record['roster'].items():
        if not pin['ignoredLargeAsset']:assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    plan=load(root/'execution-plan.json')
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','docs/')):assert sha(REPO/name)==pin
    failure=load(root/'failure.json');final=load(root/'container-result.json');metrics=load(root/'metrics.json')
    assert failure['status']=='water_coordinate_closure_stopped' and failure['error']=="PilotError('Water reference compressed output cap')"
    assert failure['phase']=='source-coordinate-capture'
    assert final['State']['ExitCode']==final['clientExitCode']==load(root/'run-summary.json')['exitCode']==2
    assert not final['State']['OOMKilled'] and load(root/'cleanup.json')['removed'] and load(root/'cleanup.json')['independentInspectAbsent']
    events=dict(line.split() for line in metrics['memory.events'].splitlines())
    assert events['oom']==events['oom_kill']==metrics['memory.swap.max']=='0' and int(metrics['memory.peak'])<=4294967296
    assert record['terminalRecord']=='failure.json' and 'receipt.json' not in record['roster'] and 'report.json' not in record['roster']
    assert sum(p['bytes'] for n,p in record['roster'].items() if n.endswith('.gz'))==411411168
    assert record['usage']['conservativeAllocatedBytes']==427286528<469762048
    return {**result,'waterCoordinateV1PreservedStorageStop':True,'waterCoordinateV1SourceOrCoordinateCompletionEstablished':False,
            'newUniqueClosedAllocationBytes':3776536576,'uniqueClosedRoots':132,
            'waterNationalCoordinateCaptureCompleted':False,'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
