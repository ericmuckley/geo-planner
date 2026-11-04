"""Read small mirrors/stored independent proof; never replays the large audit."""
from verify_v1 import HERE,REPO,sha,load,check,verify
for stage in ('controls','run'):verify(stage)
freeze=load(HERE/'audit-freeze-v1.json');plan=load(HERE/'audit-plan-v1.json');raw=HERE/'raw-audit-v1';closed=load(HERE/'closed-audit-v1.json')
check(sha(HERE/'audit-plan-v1.json')==freeze['recipeSha256']==sha(raw/'execution-plan.json'),'Audit recipe binding')
for name,pin in closed['files'].items():
    p=raw/name;check(p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],'Audit closed mirror '+name)
for name,pin in plan['hostFiles'].items():
    if not name.startswith('data/'):check(sha(REPO/name)==pin,'Audit repository binding '+name)
initial=load(raw/'container-initial.json');host=initial['HostConfig'];final=load(raw/'container-result.json');metrics=load(raw/'metrics.json');events=dict(line.split() for line in metrics['memory.events'].splitlines())
check(initial['Image']==plan['image'] and host['Memory']==host['MemorySwap']==2147483648 and host['NanoCpus']==1000000000 and host['NetworkMode']=='none' and host['ReadonlyRootfs'] and all(not m['RW'] for m in initial['Mounts'] if m['Destination']!='/work'),'Audit isolation')
check(final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled'] and closed['independentWorkerAbsent'] and load(raw/'cleanup.json')['independentInspectAbsent'],'Audit closed lifecycle')
check(metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and events['oom']==events['oom_kill']=='0','Audit actual memory/OOM')
a=load(raw/'audit.json');report=load(HERE/'raw-run-v1/report.json')
check(a['auditorSha256']==sha(HERE/'audit_v1.py') and a['oracleSha256']==sha(REPO/'docs/evidence/coarse-osm-backbone-prototype-2026-10-31/verify_run_v1.py') and a['closedSha256']==sha(HERE/'closed-run-v1.json') and a['reportSha256']==sha(HERE/'raw-run-v1/report.json'),'Independent audit bindings')
check(a['primitiveEdgesChecked']==report['primitiveEdges']==148961 and a['contractedEdgesChecked']==report['contractedEdges']==59073 and a['anchorsChecked']==report['anchors']==53672,'Every source edge/anchor')
check(a['selectedNativePointsChecked']==report['selectedNativeNodes']==143560 and a['geometryOccurrencesChecked']==report['geometryNodeOccurrences']==208034 and a['internalNativeAliasesChecked']==report['internalNativePoints']==89888 and a['sourceWayMetadataPartitionsChecked']==report['selectedWays']==28995,'Complete source geometry/provenance/aliases')
check(a['components']==41 and a['originalNativeQueryPairsChecked']==41 and a['internalQueryEndpointsChecked']==8,'Original complete cases and internal-point access')
check(all(a[key] in (0,False) for key in ('pbfOrFineReads','applicationDbReads','modelChanged','carPolicyReviewed','etaQualified','nationalArtifactBuilt','vercelQualified')),'No source/model/ETA/fit admission')
stop=load(HERE/'closure-stop-audit-v1.json');check(stop['closerSha256']==sha(HERE/'close_v1.py') and stop['workerAnalysisSuccessful'] and not stop['producerOrAuditReplayed'] and not stop['partialMirrorCreated'],'Preserved V1closure stop;V2closed unchanged audit')
print('PASS: complete independent source geometry/metadata/native-point lineage/serializedCSR/41original queries; all workers closed; closure correction preserved')
