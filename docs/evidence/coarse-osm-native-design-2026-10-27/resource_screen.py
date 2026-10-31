"""Design arithmetic only. Reads no road data, native tools or runtime state."""
import json

NODES = 1606229364
ROWS = 4096
BLOCKS_PER_SHARD = 512
INDEX_LIMIT = 24 * 1024**3
WORK_LIMIT = 64 * 1024**3


def bound(nodes, maximum_id):
    assert 0 < nodes <= maximum_id < 2**63
    blocks = (nodes + ROWS - 1) // ROWS
    shards = (blocks + BLOCKS_PER_SHARD - 1) // BLOCKS_PER_SHARD
    deltas = nodes - blocks
    # Total within-block gaps cannot exceed the complete monotone ID span.
    varints = deltas + sum(min(deltas, (maximum_id - 1) // 128**k) for k in range(1, 9))
    overhead = 96 * blocks + 128 * shards + 4096 + 16 * 1024**2
    # Reserve 4KiB rounding per shard and index sidecar. Not full FS metadata.
    allocation_reserve = 4096 * (shards + 3)
    total = 8 * nodes + varints + overhead + allocation_reserve
    return {'nodes': nodes, 'assumedMaximumId': maximum_id, 'blocks': blocks, 'shards': shards,
        'coordinateBytes': 8 * nodes, 'idVarintBytesUpperBound': varints,
        'headerDirectoryReceiptBytes': overhead, 'allocationRoundingReserveBytes': allocation_reserve,
        'indexBytesUpperBound': total, 'marginedIndexBytes': (3 * total + 1) // 2,
        'perIndexScreenPassesConditionally': (3 * total + 1) // 2 <= INDEX_LIMIT}


def result():
    illustrative = bound(NODES, 2**40 - 1)
    worst = bound(NODES, 2**63 - 1)
    low, high = NODES, 2**63 - 1
    while low < high:
        middle = (low + high + 1) // 2
        if bound(NODES, middle)['perIndexScreenPassesConditionally']:
            low = middle
        else:
            high = middle - 1
    shard_peak = 4096 * 512 * 17 + 64 * 512 + 128
    retained = {'originalOtherWorkingBytes': 13730880848, 'oldUntrustedIndexBytesReserved': 8783028224,
        'qualifiedRuntimeImageBytes': 191505175, 'newBuildClosureReservationBytes': 14 * 1024**3,
        'earlierSmallOutputsReservationBytes': 1024**3}
    # The retired primary directory/receipts coexist with the complete audit index.
    extra_sidecars = 32 * illustrative['blocks'] + 4096 + 16 * 1024**2 + 3 * 4096
    working = sum(retained.values()) + illustrative['marginedIndexBytes'] + (3 * (shard_peak + extra_sidecars) + 1) // 2
    return {'scope': 'Conditional format arithmetic, not measured size, throughput, ID range or full-import admission.',
        'illustrativeBound': illustrative, 'fullSigned63IdDomain': worst,
        'largestMaximumIdPassingThisBound': low, 'actualNationalMaximumId': None,
        'maximumReplacementShardBytes': shard_peak, 'retainedReadOnlyAndOtherReservations': retained,
        'additionalPrimaryDirectoryAndReceiptBytes': extra_sidecars,
        'conditionalMarginedWorkingBytes': working, 'workingLimitBytes': WORK_LIMIT,
        'conditionalWorkingSlackBytes': WORK_LIMIT - working,
        'unproven': ['National maximum ID; sample IDs do not establish it.',
            'Actual compiler image/header/lib closure and expanded bytes within the reserved14GiB.',
            'Measured allocation/FS metadata, lookup latency, memory and two-pass runtime.',
            'Native guard/ABI/selection/semantic-seal/canonical fallback equivalence.'],
        'futureNodePrefixGateSeconds': .070, 'futureMarginedTwoNodePassForecastSecondsAtGate': 4 * NODES * .070 / 64000,
        'oldWorkSeconds': 14340, 'otherWorkSecondsRemainingAtGate': 14340 - 4 * NODES * .070 / 64000,
        'futureSampleObjectLimit': 200000, 'futureSampleAggregateLimit': 2000000,
        'fullImportAdmitted': False, 'anyNewNationalScan': False}


if __name__ == '__main__':
    print(json.dumps(result(), indent=2))
