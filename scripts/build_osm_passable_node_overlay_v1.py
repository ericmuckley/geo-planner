"""One bounded host-only graph-node flag overlay; original graph/source stays read-only."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from coarse_osm_car_passable_barriers_v1 import POLICY
from coarse_osm_country_screen_v1 import owned_usage
from coarse_osm_passable_node_overlay_v1 import audit_overlay,build_overlay
from coarse_timing_input import require,start_watchdog

REPO=Path(__file__).resolve().parents[1]
OUTPUT='data/coarse-quality/us-osm-passable-node-overlay-v1'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('pin');args=parser.parse_args()
    began=time.monotonic();recipe=REPO/args.plan
    require(sha(recipe)==args.pin,'Passable node overlay recipe binding')
    plan=json.loads(recipe.read_bytes())
    require(plan['output']==OUTPUT and plan['policy']==POLICY,'Passable overlay fixed namespace/policy')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864<72*1024**3,'Passable overlay aggregate reserve')
    for name,pin in plan['bindings'].items():
        require(not name.endswith(('.pbf','/001.bin')) and sha(REPO/name)==pin,'Passable overlay exact readonly input: '+name)
    root=REPO/OUTPUT;root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    timer=start_watchdog(120)
    def check():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        require(time.monotonic()-began<120 and rss<=536870912,'Passable overlay host deadline/RSS')
        require(owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Passable overlay owned cap')
        return rss
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=1048576,'Passable overlay bounded small report')
        with (root/name).open('xb') as stream:stream.write(raw)
    def decoded(name,cap):
        with gzip.open(REPO/plan[name],'rb') as stream:raw=stream.read(cap+1)
        require(len(raw)<=cap and hashlib.sha256(raw).hexdigest()==plan[name+'RawSha256'],'Passable overlay complete raw tag/mapping seal')
        return json.loads(raw)
    try:
        check();nodes=decoded('mapping',2097152);evidence=decoded('tagEvidence',16777216)
        require(len(nodes)==evidence['selectedNodes']==13776 and not evidence['unknownRawNodeIds'],'Complete original blockers/tags')
        original=(REPO/plan['nodeFlags']).read_bytes()
        require(len(original)==5731903,'Current physical vertex count')
        proposed,changed=build_overlay(original,nodes,evidence['nodeEvidence']);check()
        with (root/'proposed-node-flags.u8').open('xb') as stream:stream.write(proposed)
        raw=(json.dumps(changed,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        require(len(raw)<=33554432,'Complete changed-node evidence cap')
        with (root/'changed-nodes.json.gz').open('xb') as stream:stream.write(gzip.compress(raw,mtime=0))
        vertices=[row['vertex'] for row in changed]
        identities=sorted(int(row['sourceNodeId']) for row in changed)
        with (root/'opened-vertices.u32').open('xb') as stream:stream.write(b''.join(struct.pack('<I',v) for v in vertices))
        with (root/'opened-node-ids.u64').open('xb') as stream:stream.write(b''.join(struct.pack('<Q',v) for v in identities))
        # Reopen output bytes and independently re-enumerate every original vertex.
        audited=audit_overlay(original,(root/'proposed-node-flags.u8').read_bytes(),nodes,evidence['nodeEvidence'])
        require(audited['changedVertices']==vertices,'Independent complete flag diff matches declared openings')
        require(list(struct.iter_unpack('<I',(root/'opened-vertices.u32').read_bytes()))==[(v,) for v in vertices],'Every opened vertex byte exact')
        require(list(struct.iter_unpack('<Q',(root/'opened-node-ids.u64').read_bytes()))==[(v,) for v in identities],'Every native uint64 opening exact')
        require(gzip.decompress((root/'changed-nodes.json.gz').read_bytes())==raw,'Every changed original tag/decision exact')
        max_rss=check();artifacts={}
        for name in ('proposed-node-flags.u8','changed-nodes.json.gz','opened-vertices.u32','opened-node-ids.u64'):
            path=root/name;artifacts[name]={'bytes':path.stat().st_size,'sha256':sha(path)}
        save('report.json',{'status':'complete_source_qualified_passable_node_flags_independently_audited','recipeSha256':args.pin,
             'policy':POLICY,'originalGraphVertices':len(original),'allOriginalBlockersAndRawTagsReplayed':len(nodes),
             'openedVertices':len(changed),'openedBarrierCounts':dict(Counter(row['rawTags']['barrier'] for row in changed)),
             'allVertexFlagsIndependentlyCompared':audited['allVertexFlagsIndependentlyCompared'],
             'remainingBlockedVertices':audited['remainingBlockedVertices'],
             'signalsAndReversalBitsExact':audited['signalsAndReversalBitsExact'],
             'everyOldUnblockedVertexExact':True,'everyIndependentRestrictionContributorRetained':True,
             'artifacts':artifacts,'sourcePbfReads':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
             'appActivated':False,'routingOrAccuracyAccepted':False,
             'hostSecondsIncludingBindingsConstructionAllFlagAndTagAudits':time.monotonic()-began,'hostMaximumRssBytes':max_rss,
             'scope':'All 13,776 current graph blockers independently classified under the single frozen generic source-tag policy. Every 5,731,903 vertex flag independently compared; old positive vertices, signals, reversal bits and independent restriction contributors retained. Only qualified blocker bits change in a separate prototype artifact; original source/graph/costs/turns stay read-only. Host 512 MiB RSS/120s/64 MiB owned bounds, not cgroup/CPU/cloud evidence. No new routing, map, point, accuracy or app admission.'})
    except BaseException as error:
        save('failure.json',{'status':'passable_node_overlay_stopped','error':repr(error)});raise
    finally:
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


if __name__=='__main__':main()
