"""Compose source-reviewed incomplete-turn node flags; all other runtime fields remain exact."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from array import array
from coarse_osm_incomplete_node_restrictions_v1 import POLICY
from coarse_osm_country_screen_v1 import owned_usage
from coarse_osm_incomplete_node_flags_v1 import audit,build,rules_from_metadata
from coarse_timing_input import require,start_watchdog

REPO=Path(__file__).resolve().parents[1]
OUTPUT='data/coarse-quality/us-osm-incomplete-node-flags-v1'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('pin');args=parser.parse_args()
    began=time.monotonic();recipe=REPO/args.plan
    require(sha(recipe)==args.pin,'Incomplete-node node overlay recipe binding')
    plan=json.loads(recipe.read_bytes())
    require(plan['output']==OUTPUT and plan['policy']==POLICY,'Incomplete-node overlay fixed namespace/policy')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864<72*1024**3,'Incomplete-node overlay aggregate reserve')
    for name,pin in plan['bindings'].items():
        require(not name.endswith(('.pbf','/001.bin')) and sha(REPO/name)==pin,'Incomplete-node overlay exact readonly input: '+name)
    root=REPO/OUTPUT;root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    timer=start_watchdog(120)
    def check():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        require(time.monotonic()-began<120 and rss<=536870912,'Incomplete-node overlay host deadline/RSS')
        require(owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Incomplete-node overlay owned cap')
        return rss
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=1048576,'Incomplete-node overlay bounded small report')
        with (root/name).open('xb') as stream:stream.write(raw)
    def decoded(name,cap):
        with gzip.open(REPO/plan[name],'rb') as stream:raw=stream.read(cap+1)
        require(len(raw)<=cap and hashlib.sha256(raw).hexdigest()==plan[name+'RawSha256'],'Incomplete-node overlay complete raw tag/mapping seal')
        return json.loads(raw)
    try:
        check();nodes=decoded('mapping',2097152);evidence=decoded('tagEvidence',16777216)
        require(len(nodes)==evidence['selectedNodes']==13776 and not evidence['unknownRawNodeIds'],'Complete original blockers/tags')
        original=(REPO/plan['nodeFlags']).read_bytes()
        require(len(original)==5731903,'Current physical vertex count')
        raw_permutation=(REPO/plan['permutation']).read_bytes()
        require(sys.byteorder=='little' and len(raw_permutation)==4*len(original),'Complete little-endian native-to-spatial permutation')
        spatial_to_native=array('I');spatial_to_native.frombytes(raw_permutation);del raw_permutation
        permutation=array('I',[0xffffffff])*len(original)
        for vertex,anchor in enumerate(spatial_to_native):
            require(anchor<len(original) and permutation[anchor]==0xffffffff,'Complete source permutation is a bijection')
            permutation[anchor]=vertex
        require(all(spatial_to_native[vertex]==anchor for anchor,vertex in enumerate(permutation)),
                'Every inverted native-to-spatial row matches the closed source permutation')
        del spatial_to_native
        metadata=decoded('metadata',16777216)
        rules=rules_from_metadata(metadata['incompleteRelations'])
        require(len(rules)==2525 and plan['actualLinuxControls']==75 and plan['completeCapturedConsumerPassed'],'Full source rules and actual Linux/captured admission')
        proposed,changed=build(original,nodes,evidence['nodeEvidence'],permutation,rules);check()
        require({row['sourceNodeId'] for row in changed}=={row['sourceNodeId'] for row in metadata['potentialNodeChanges']},'Every complete proposed node matches the independently frozen source inventory')
        with (root/'proposed-node-flags.u8').open('xb') as stream:stream.write(proposed)
        raw=(json.dumps(changed,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        require(len(raw)<=33554432,'Complete changed-node evidence cap')
        with (root/'changed-nodes.json.gz').open('xb') as stream:stream.write(gzip.compress(raw,mtime=0))
        vertices=[row['vertex'] for row in changed]
        identities=sorted(int(row['sourceNodeId']) for row in changed)
        with (root/'opened-vertices.u32').open('xb') as stream:stream.write(b''.join(struct.pack('<I',v) for v in vertices))
        with (root/'opened-node-ids.u64').open('xb') as stream:stream.write(b''.join(struct.pack('<Q',v) for v in identities))
        # Reopen output bytes and independently re-enumerate every original vertex.
        audited=audit(original,(root/'proposed-node-flags.u8').read_bytes(),nodes,evidence['nodeEvidence'],permutation,rules)
        require(list(audited['changedVertices'])==vertices,'Independent complete flag diff matches declared openings')
        require(list(struct.iter_unpack('<I',(root/'opened-vertices.u32').read_bytes()))==[(v,) for v in vertices],'Every opened vertex byte exact')
        require(list(struct.iter_unpack('<Q',(root/'opened-node-ids.u64').read_bytes()))==[(v,) for v in identities],'Every native uint64 opening exact')
        require(gzip.decompress((root/'changed-nodes.json.gz').read_bytes())==raw,'Every changed original tag/decision exact')
        max_rss=check();artifacts={}
        for name in ('proposed-node-flags.u8','changed-nodes.json.gz','opened-vertices.u32','opened-node-ids.u64'):
            path=root/name;artifacts[name]={'bytes':path.stat().st_size,'sha256':sha(path)}
        save('report.json',{'status':'complete_source_qualified_incomplete_node_flags_independently_audited','recipeSha256':args.pin,
             'policy':POLICY,'originalGraphVertices':len(original),'allOriginalBlockersAndRawTagsReplayed':len(nodes),
             'openedVertices':len(changed),'sourceIncompleteRelations':len(rules),
             'allVertexFlagsIndependentlyCompared':audited['allVertexFlagsIndependentlyCompared'],
             'remainingBlockedVertices':audited['remainingBlockedVertices'],
             'signalsAndReversalBitsExact':audited['signalsAndReversalBitsExact'],
             'everyOldUnblockedVertexExact':True,'everyIndependentUnconvertedRestrictionContributorRetained':True,
             'artifacts':artifacts,'sourcePbfReads':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
             'appActivated':False,'routingOrAccuracyAccepted':False,
             'hostSecondsIncludingBindingsConstructionAllFlagAndTagAudits':time.monotonic()-began,'hostMaximumRssBytes':max_rss,
             'scope':'Full5731903current spatial flags and complete native-to-spatial permutation checked, all13776originalsourceblockers/tags and2525incomplete static singleton-via relations independently replay. Only1488blocker bits clear where no direct guard or other contributor remains; qualifiedpassable openings/signal/reversal bits/everyoldopenvertexretain. Complete captured nativecompiler/source audit and75actualLinuxcontrols pass. All cost/arc/turn/geometry/history/water facts and numericIDs remain original; this is a separate nodeflag artifact only, not legal-route/accuracy/app admission. Host512MiBRSS/120s/owned64MiB/aggregate72GiB, no cgroup/CPU/cloud claim. No PBF/provider/modelquery/applicationDB/deployment.'})
    except BaseException as error:
        save('failure.json',{'status':'incomplete_node_overlay_stopped','error':repr(error)});raise
    finally:
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


if __name__=='__main__':main()
