"""Bounded read-only topology diagnosis of saved continuous matcher candidates."""
import json
import math
import os
from pathlib import Path
import unittest

from coarse_osm_corridor_families_v1 import family,summary
from coarse_osm_records import canonical
from coarse_path_features import distance_km
from coarse_timing_input import require


def lines(path,cap,check):
    with Path(path).open('rb') as stream:
        while raw:=stream.readline(cap+1):
            check();require(len(raw)<=cap and raw.endswith(b'\n'),'Corridor analysis bounded JSON row');yield json.loads(raw)


def run(plan,output):
    import coarse_osm_corridor_families_v1_test as tests
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    require(result.wasSuccessful() and result.testsRun==8 and not result.skipped,'Corridor synthetic controls failed')
    output.write('controls.json',canonical({'tests':8,'successful':True,'skips':0})+b'\n')
    root=Path('/inputs/run');original=list(lines('/inputs/census.jsonl',4194304,output.check));source={(r['windowId'],r['arc']):r for r in original}
    require(len(original)==len(source)==2469,'Corridor complete original source roster')
    parent=json.loads((root/'report.json').read_bytes());windows=parent['windows'];require(len(windows)==21,'Corridor all areas')
    records=[];seen=set()
    for window in windows:
        wid=window['id'];path=root/'windows'/wid;bindings={r['ordinal']:r for r in lines(path/'part-bindings.jsonl',plan['maxLineBytes'],output.check)};selected=[]
        for match in lines(path/'matches.jsonl',plan['maxLineBytes'],output.check):
            key=match['windowId'],match['arc'];require(key in source and key not in seen and key[0]==wid,'Corridor original identity/window');seen.add(key);original=source[key]
            require(match['sourceClassKph']==original['sourceClassKph'] and math.isclose(match['sourceKm'],original['sourceKm'],abs_tol=1e-9),'Corridor unchanged source class/km')
            weights=[]
            for a,b,km in original['sourceSpans']:
                n=max(1,math.ceil(distance_km(a,b)/.025));weights.extend([km/n]*n)
            record=family(match,bindings,weights);output.record('families.jsonl',record);records.append(record);selected.append(record)
        output.write('windows/'+wid+'.json',canonical({'id':wid,'totals':summary(selected),'classes':{str(k):summary([r for r in selected if r['sourceClassKph']==k]) for k in (85,105)}})+b'\n')
    require(seen==set(source),'Corridor no omitted original record')
    report={'format':'native-osm-saved-corridor-topology-v1','allWindows':summary(records),'classes':{str(k):summary([r for r in records if r['sourceClassKph']==k]) for k in (85,105)},
            'originalSourceKm':parent['allWindows']['sourceKm'],'originalSamples':parent['allWindows']['samples'],'sourceAdequacyQualified':False,'physicalMatchQualified':False,'usableLimitOrMatchingQualified':False,'modelChanged':False,
            'scope':'Descriptive topology of existing saved candidate paths only. Overlapping subpaths may form one unbranched connected native-ID corridor; true branches/cycles/disconnected alternatives remain ambiguous. Numeric/role opportunity still ignores access/direction/grade/source/physical applicability and all rejected alternatives. No new matching, changed thresholds, omitted cases, routing model or nationwide accuracy.'}
    require(report['allWindows']['arcWindowRecords']==2469 and report['allWindows']['samples']==85629,'Corridor unchanged sample/record counts')
    output.write('report.json',canonical(report)+b'\n')
    cgroup=Path('/sys/fs/cgroup');tmp=os.statvfs('/tmp')
    output.write('metrics.json',canonical({name:(cgroup/name).read_text().strip() for name in ('memory.max','memory.swap.max','memory.peak','memory.events','cpu.max')}|{'tmpBytes':tmp.f_blocks*tmp.f_frsize})+b'\n')


if __name__=='__main__':
    from offline_timing_runner import main
    main('docs/evidence/coarse-osm-extraction-2026-10-30/corridor-family-plan-v1.json')
