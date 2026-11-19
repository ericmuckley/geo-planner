"""Independent complete node-flag decode and exact original core/history byte comparison."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_packed_codec_audit_v1 import decode


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('pin');args=parser.parse_args()
    began=time.monotonic();repo=Path(__file__).resolve().parents[1];recipe=repo/args.plan
    assert sha(recipe)==args.pin
    plan=json.loads(recipe.read_bytes())
    assert plan['output']=='data/coarse-quality/us-osm-incomplete-node-wire-audit-v2'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+8388608<72*1024**3
    for name,pin in plan['bindings'].items():assert sha(repo/name)==pin,name
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def check():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        assert time.monotonic()-began<120 and rss<536870912
        return rss
    try:
        wire=repo/plan['wire'];parent=repo/plan['source']
        closed=json.loads((repo/plan['wireClosed']).read_bytes());prior=json.loads((repo/plan['sourceClosed']).read_bytes())
        assert closed['root']==plan['wire'] and prior['root']==plan['source']
        manifests={};old={}
        for kind in ('core','context'):
            path=wire/kind/'manifest.json';assert sha(path)==closed['roster'][kind+'/manifest.json']['sha256']
            manifests[kind]=json.loads(path.read_bytes())
            path=parent/kind/'manifest.json';assert sha(path)==prior['roster'][kind+'/manifest.json']['sha256']
            old[kind]=json.loads(path.read_bytes())
        assert manifests['core']['format']==old['core']['format']=='packed-integer-delta-byteplanes-gzip-v1'
        assert manifests['context']['format']==old['context']['format']=='static-via-way-context-gzip-v1'
        assert manifests['core']['requiresTurnContextSearch'] is True
        assert manifests['context']['graphCoreManifestSha256']==sha(wire/'core/manifest.json')
        assert manifests['core']['parentCoreManifestSha256']==sha(parent/'core/manifest.json')
        assert manifests['core']['nodeFlagOverlayReportSha256']==manifests['context']['nodeFlagOverlayReportSha256']==sha(repo/plan['overlayReport'])
        assert manifests['core']['contextRecordsReportSha256']==manifests['context']['contextRecordsReportSha256']==old['core']['contextRecordsReportSha256']
        epoch=json.loads((repo/plan['contextRecordsReport']).read_bytes())
        assert manifests['core']['contextRecordsReportSha256']==sha(repo/plan['contextRecordsReport'])
        assert manifests['context']['graphArcCount']==old['context']['graphArcCount']==epoch['retainedArcsMapped']==plan['graphArcCount']
        copied={'core':0,'context':0};decoded_bytes=context_bytes=compressed=0
        for kind in ('core','context'):
            assert set(manifests[kind]['fields'])==set(old[kind]['fields'])
            for name,field in manifests[kind]['fields'].items():
                check();assert field['file']=='fields/'+Path(name).name+'.gz'
                relative=kind+'/'+field['file'];path=wire/relative
                assert path.stat().st_size==field['compressedBytes']<=67108864
                assert sha(path)==field['compressedSha256']==closed['roster'][relative]['sha256']
                compressed+=field['compressedBytes']
                if kind=='core' and name=='routing/node-flags.u8':
                    assert (field['wordBytes'],field['lanes'])==(1,1)
                    with gzip.open(path,'rb') as stream:raw=stream.read(field['rawBytes']+1)
                    assert len(raw)==field['rawBytes']==5731903
                    restored=decode(raw,1,1)
                    assert restored==(repo/plan['nodeFlags']).read_bytes()
                    assert hashlib.sha256(restored).hexdigest()==field['rawSha256']
                    decoded_bytes=len(restored)
                else:
                    assert field==old[kind]['fields'][name]
                    assert sha(parent/relative)==prior['roster'][relative]['sha256']
                    assert path.read_bytes()==(parent/relative).read_bytes()
                    copied[kind]+=1
                    if kind=='context':
                        with gzip.open(path,'rb') as stream:raw=stream.read(field['rawBytes']+1)
                        assert len(raw)==field['rawBytes'] and hashlib.sha256(raw).hexdigest()==field['rawSha256']
                        context_bytes+=len(raw)
        assert copied=={'core':12,'context':6} and context_bytes==epoch['contextRuntimeBackingBytes']==plan['contextRawBytes'] and decoded_bytes==5731903
        report={'status':'independent_complete_source_qualified_node_wire_audit_passed','recipeSha256':args.pin,
                'copiedCoreFieldsByteIdentical':copied['core'],'copiedContextFieldsByteIdentical':copied['context'],
                'replacementNodeFlagBytesIndependentlyDecoded':decoded_bytes,'contextRawBytesIndependentlyAuthenticated':context_bytes,
                'combinedCoreAndContextCompressedBytes':compressed,'coreAndContextBindingsExact':True,
                'hostSecondsIncludingBindingsAllCopyAndDecodeChecks':time.monotonic()-began,'hostMaximumRssBytes':check(),
                'sourcePbfReads':0,'routingQueries':0,'nativeProducerExecutions':0,'providerRequests':0,'appActivated':False,
                'scope':'Every changed node-flag byte independently Python-decodes to the complete source-audited overlay. All twelve other physical packets and six history packets are exact sealed copies; every history raw byte hash independently recomputes. New core/context/policy/parent bindings exact. No actual loader/query/access/map/accuracy, app memory/package/first-estimate or cloud admission. Host512MiBRSS/120s only.'}
        with (root/'report.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
        print(json.dumps(report))
    except BaseException as error:
        with (root/'failure.json').open('x') as stream:json.dump({'error':repr(error)},stream);stream.write('\n')
        raise


if __name__=='__main__':main()
