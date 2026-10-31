"""Saved complete-prefix measurement; no PBF, native or ignored-part reads."""
import json
import subprocess
import sys

from verify_prefix_controls_v2 import REPORT,closed,load


def main():
    subprocess.run([sys.executable,'-B',str(REPORT/'verify_prefix_controls_v2.py')],check=True,stdout=subprocess.DEVNULL)
    plan,mirror=closed('run','v2');old=load(REPORT/'cell-census-closed-run-v1.json')
    expected=[{'path':old['root']+'/'+name,**{key:item[key] for key in ('bytes','sha256')}} for name,item in old['roster'].items() if item.get('ignoredPart')]
    assert plan['parts']==expected and len(expected)==31
    result=load(mirror/'result.json');parts=[load(mirror/f'part-{i:04d}.json') for i in range(31)]
    totals={key:sum(part[key] for part in parts) for key in result['totals']}
    assert totals==result['totals'] and result['status']=='passed_prefix_conversion'
    assert totals=={'blocks':373002,'rows':1527816192,'oldBytes':2080277463,'newBytes':914994196,'oldIdBytes':1536804979,'newIdBytes':370029704,'idRunBlocks':346810,'rawIdBlocks':26192,'cellRuns':129527087}
    previous=0
    for part,pin in zip(parts,expected):
        assert part['oldSha256']==pin['sha256'] and part['oldBytes']==pin['bytes']
        assert previous<part['first']<=part['last'];previous=part['last']
        assert part['everyIdAndCellNativeRoundtrip'] and part['newBytes']<=part['oldBytes']+4*part['blocks']
        assert part['idRunBlocks']+part['rawIdBlocks']==part['blocks'] and len(part['convertedSha256'])==64
    assert totals['newBytes']==totals['oldBytes']+4*totals['blocks']+totals['newIdBytes']-totals['oldIdBytes']
    assert result['codecRows']==2*totals['rows'] and result['codecCalls']==2*totals['blocks']
    assert result['inputUnchanged'] and not result['nationalSourceRead'] and not result['fullFineIndexRead'] and not result['completeBankCapacityQualified'] and not result['modelChanged']
    state=load(mirror/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
    metrics=load(mirror/'metrics-end.json');assert int(metrics['latest']['cgroup']['memory.peak'])<=4294967296
    assert 'oom_kill 0' in metrics['latest']['cgroup']['memory.events']
    assert metrics['observedWorkPeaks']['conservativeAllocatedBytes']<plan['ownedBytes']
    print(json.dumps({'prefixLosslessMeasurementPassed':True,'rows':totals['rows'],'oldBytes':totals['oldBytes'],'newBytes':totals['newBytes'],'reductionPercent':100*(1-totals['newBytes']/totals['oldBytes']),'workerAbsent':True,'completeNationalCapacityQualified':False}))


if __name__=='__main__':main()
