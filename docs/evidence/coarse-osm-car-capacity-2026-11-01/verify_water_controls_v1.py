"""Portable water/source qualification, preserving all failed predecessor evidence."""
import json
from verify_entry_diagnosis_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, closed, load, sha


def verify():
    result = previous()
    stopped = load(HERE/'water-census-build-preinput-stop-v1.json')
    assert not stopped['workerCreated'] and not stopped['outputCreated'] and not stopped['sourceRead']
    assert stopped['recipeSha256'] == sha(HERE/stopped['recipe'])
    root, _ = closed('water-census', 'build', 'v2', 0)
    built = load(root/'result.json')
    assert built['artifactSha256'] == '10b3883a592adcb0fb010113fc6ed5eed290e47ad8f74cd91369a0728baa7157'
    assert built['artifactBytes'] == 2006640
    root, _ = closed('water-census', 'controls', 'v2', 2)
    assert load(root/'controls.json') == {'tests':31,'successful':False,'failures':0,'errors':29,'skips':0}
    root, _ = closed('water-census', 'controls', 'v3', 0)
    assert load(root/'controls.json') == {'tests':32,'successful':True,'failures':0,'errors':0,'skips':0}
    pipeline = stage('water-source-controls', True)
    assert pipeline['checks'] == {'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False}
    assert pipeline['tiny']['receipt']['counts'] == {'node':4,'way':3,'relation':2}
    assert pipeline['tiny']['receipt']['nativeEof'] and pipeline['tiny']['receipt']['pythonProjectionFrames'] == 0
    assert pipeline['tiny']['water']['waterWays'] == pipeline['tiny']['water']['waterRelations'] == 1
    return {**result, 'waterSourceLinuxControls':32,'waterControllerTinyPipelineAndWrongSourceChecks':True,
            'waterNationalSourceCensusCompleted':False,'newUniqueClosedAllocationBytes':2858164224,
            'uniqueClosedRoots':114,'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))
