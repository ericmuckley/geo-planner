"""Portable isolated-reader control proof, without source or container operations."""
import json
from verify_entry_capture_v1 import verify as previous
from verify_preparation_v1 import HERE, load
from verify_spatial_storage_v1 import host_closed


def verify():
    result = previous()
    failed = load(HERE/'relation-metadata-controls-closed-v1.json')
    assert failed['terminalRecord'] == 'failure.json'
    root = host_closed('relation-metadata-controls-v2')
    report = load(root/'report.json')
    assert report['status'] == 'isolated_relation_metadata_controls_passed'
    assert report['controls'] == {'tests': 16, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    assert report['sourcePbfReads'] == report['hostedRequests'] == 0
    metrics = load(root/'metrics.json')
    assert metrics['memoryPeakBytes'] == 23609344 and metrics['swapCurrentBytes'] == 0
    assert int(metrics['memoryEvents']['oom']) == int(metrics['memoryEvents']['oom_kill']) == 0
    for prefix in ['relation-metadata-controls', 'relation-metadata-controls-v2']:
        cleanup = load(HERE/f'{prefix}-raw-v1/cleanup.json')
        assert cleanup['removed'] and cleanup['independentInspectAbsent']
    return {**result, 'isolatedNationalRelationReaderControls': 16,
            'newUniqueClosedAllocationBytes': 2361155584, 'uniqueClosedRoots': 89,
            'nationalRelationMetadataRunCompleted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
