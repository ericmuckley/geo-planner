"""Portable paid-shape/source audit, storage and loader proof; no producer replay."""
import json
from verify_preparation_v1 import HERE,REPO,closed,load,sha
from verify_spatial_storage_v1 import host_closed
from verify_wire_codec_v1 import verify as core


def verify():
    core()
    results={}
    for stage in ('build','controls','captured','captured-audit','country','country-audit'):
        root,plan=closed('paid-geometry',stage,'v1',0)
        for group in ('producerBindings','parentRecordBindings'):
            for name,pin in plan[group].items():assert sha(REPO/name)==pin,name
        results[stage]=load(root/'result.json')
        if stage.endswith('audit'):
            assert 'artifact' not in plan and not any('coarse_osm_car_paid_geometry_v1.' in name for name in plan['mounts'])
            assert results[stage]['nativeProducerExecutions']==results[stage]['sourcePbfReads']==0
            assert not results[stage]['originSnapOrEtaOrAppQualified']
    assert results['build']['artifactSha256']=='b02ad89a559c3848c13a7e1d1423909c20550dc36523334c4894fdcb055bacd5'
    assert results['controls']['tests']==19 and results['controls']['successful'] and results['controls']['skips']==0
    for stage,counts in [('captured',(48943,75137,325,512,365,9047)),('country',(6408084,9620680,296701,690468,529205,11469870))]:
        produced=results[stage];checked=results[stage+'-audit']
        assert checked['status']=='independent_complete_paid_geometry_source_packet_prefix_length_audit_passed'
        assert tuple(checked[key] for key in ('physicalSpansChecked','directedSourceCostsChecked','curvedSpansChecked','interiorPositionsChecked','longSpansChecked','runtimeBytes'))==counts
        for a,b in [('physicalSpans','physicalSpansChecked'),('postClosureArcs','directedSourceCostsChecked'),('interiorPoints','interiorPositionsChecked'),('runtimeBytes','runtimeBytes')]:assert produced[a]==checked[b]
        assert checked['maximumDiscardedSourcePointErrorMeters']<=100.001 and checked['maximumDiscardedSourceTimeErrorMs']<=10001
        assert checked['lengthOverflowsChecked']==0
    codec=host_closed('paid-geometry-codec');manifest=load(codec/'manifest.json');compression=load(codec/'report.json')
    assert compression['rawBytes']==11469870 and compression['compressedBytes']==7895857 and len(manifest['fields'])==7
    original=load(HERE/'paid-geometry-closed-country-v1.json')['roster']
    for name,row in manifest['fields'].items():assert row['rawBytes']==original[name]['bytes'] and row['rawSha256']==original[name]['sha256']
    audit=load(host_closed('paid-geometry-codec-audit')/'report.json')
    assert audit['status']=='independent_complete_paid_geometry_storage_bytes_passed' and audit['bytesIndependentlyDecodedAndCompared']==11469870
    profile=load(host_closed('paid-geometry-profile')/'report.json')
    assert profile['status']=='host_compressed_core_paid_geometry_and_original_queries_passed'
    assert profile['compressedBytes']==53755286 and profile['retainedDataBackingBufferBytes']==140869261
    assert [q['ticks'] for q in profile['queries']]==[296763,256312,None,None]
    return {'allNationalSourceSpansIndependentlyChecked':6408084,'runtimeGeometryBytes':11469870,
            'combinedCompressedBytes':53755286,'retainedDataBackingBufferBytes':140869261,
            'hostCoreGeometryLoadAndFirstVertexQueryMs':profile['hostFirstLoadAndQueryMsIncludingGc'],
            'arbitraryOriginOrCompleteAppOrEtaQualified':False,
            'reads':'Small mirrored records and bound code only; no ignored graph, native, PBF, Docker, provider or application DB.'}


if __name__=='__main__':print(json.dumps(verify()))
