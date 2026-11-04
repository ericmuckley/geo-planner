"""Portable closed-audit proof; does not replay the large derived scan."""
from verify_v1 import HERE,REPO,sha,load,check,verify

for stage in ('build','controls','run'):verify(stage)
freeze=load(HERE/'audit-freeze-v1.json');plan=load(HERE/'audit-plan-v1.json');raw=HERE/'raw-audit-v1';closed=load(HERE/'closed-audit-v1.json')
check(sha(HERE/'audit-plan-v1.json')==freeze['recipeSha256']==sha(raw/'execution-plan.json'),'Audit recipe')
for name,pin in closed['files'].items():
    path=raw/name;check(path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256'],'Audit closed mirror '+name)
for name,pin in plan['hostFiles'].items():check(sha(REPO/name)==pin,'Audit repository binding '+name)
initial=load(raw/'container-initial.json');host=initial['HostConfig'];final=load(raw/'container-result.json');metrics=load(raw/'metrics.json');events=dict(line.split() for line in metrics['memory.events'].splitlines())
check(initial['Image']==plan['image'] and host['Memory']==host['MemorySwap']==2147483648 and host['NanoCpus']==1000000000 and host['NetworkMode']=='none' and host['ReadonlyRootfs'],'Audit isolation')
check(all(not m['RW'] for m in initial['Mounts'] if m['Destination']!='/work'),'Audit readonly source')
check(final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled'] and closed['independentWorkerAbsent'] and load(raw/'cleanup.json')['independentInspectAbsent'],'Audit closed ownership')
check(metrics['memory.max']=='2147483648' and metrics['memory.swap.max']=='0' and events['oom']==events['oom_kill']=='0','Audit actual resources')
audit=load(raw/'audit.json');topology=load(HERE/'raw-run-v1/topology.json')
check(audit['counts']==topology['counts'] and audit['sourceWaysIndependentlyCounted']==4227238 and audit['everySourceWayHasTwoEndpoints'] and audit['rawSortedMetadataExactMultisets'],'Independent actual all counts/source ways/metadata')
check(audit['authenticatedSpoolBytes']==topology['writtenBytes']==1775576920 and audit['spoolFiles']==37,'Every derived spool')
check(audit['receiptSha256']==sha(HERE/'raw-run-v1/receipt.json') and audit['topologySha256']==sha(HERE/'raw-run-v1/topology.json'),'Independent actual input seals')
d=audit['wayLineageDiagnostic'];p=audit['counts']['primitiveEdges'];n=audit['counts']['uniqueNodes'];v=d['anchors'];e=d['contractedEdges']
check(e==p-n+v and d['routingMetersF64ArrayBytes']==12*v+24*e+4 and d['fullGeometryArrayBytes']==8*n+4*p+8*e+4 and d['hypotheticalU16CostRoutingArrayBytes']==12*v+12*e+4,'Prospective lineage layout arithmetic')
check(all(audit[key] in (False,0) for key in ('sourcePbfReads','nativeLibraryExecutions','graphAllocated','modelChanged','etaQualified','nationalCoverageQualified','vercelQualified')) and d['contractedArtifactBuilt'] is False and d['carSemanticsQualified'] is False and d['compressedPackageMeasured'] is False,'No source/model/package admission')
print('PASS: complete independent national incidence/source-way/metadata/array counts; separately scoped lineage diagnostic; frozen resources and absent workers')
