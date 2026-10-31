"""Prospective screen arithmetic only; no source, native tool or service reads."""
import json

MIB = 1024**2
GIB = 1024**3
COUNTS = {"node": 1606229364, "way": 162688797, "relation": 1624265}
SOURCE_BYTES = 12229320016
ROWS = 4096
SHARD_BLOCKS = 512
SEED = 0x47504C414E4E4552  # ASCII GPLANNER, interpreted as big-endian bytes.
MASK = 2**64 - 1


def splitmix64(value):
    """Standard SplitMix64 output, with its state increment, modulo 2**64."""
    value = (value + 0x9E3779B97F4A7C15) & MASK
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK
    return value ^ (value >> 31)


def full_index_bound(nodes, maximum_id):
    """Conservative existing format bound; assumes unique monotone positive IDs."""
    assert 0 < nodes <= maximum_id < 2**63
    blocks = (nodes + ROWS - 1) // ROWS
    shards = (blocks + SHARD_BLOCKS - 1) // SHARD_BLOCKS
    deltas = nodes - blocks
    # Sum of all within-block gaps <= maximum_id-1. Count each varint tier.
    varints = deltas + sum(min(deltas, (maximum_id - 1) // 128**k) for k in range(1, 9))
    logical = 8 * nodes + varints + 96 * blocks + 128 * shards + 4096 + 16 * MIB
    # Files+3 also conservatively covers the directory, catalog and receipt.
    filesystem = (4096 + 8192) * (shards + 3) + MIB
    return {"maximumIdAssumption": maximum_id, "logicalUpperBound": logical,
            "filesystemReserve": filesystem,
            "marginedBytes": (3 * (logical + filesystem) + 1) // 2,
            "passes24GiBConditionally": (3 * (logical + filesystem) + 1) // 2 <= 24 * GIB}


def result():
    nodes = COUNTS["node"]
    blocks = (nodes + ROWS - 1) // ROWS
    shards = (blocks + SHARD_BLOCKS - 1) // SHARD_BLOCKS
    selected = [k * (shards - 1) // 7 for k in range(8)]
    selected_blocks = [min(SHARD_BLOCKS, blocks - s * SHARD_BLOCKS) for s in selected]
    selected_rows = [min(ROWS * SHARD_BLOCKS, nodes - s * ROWS * SHARD_BLOCKS) for s in selected]
    payload = 8 * ROWS + 9 * (ROWS - 1)
    shard_bytes = 128 + SHARD_BLOCKS * (64 + payload)
    # This is a reservation, not a measurement of allocation or FS metadata.
    writable = {
        "eightRetainedPlusOneReplacementShard": 9 * shard_bytes,
        "twoMiniIndexDirectoryCatalogPairs": 16 * MIB,
        "twoGlobalDirectoryCatalogPairs": 40 * MIB,
        "traceWitnessLogsReceipts": 64 * MIB,
        "scratch": 64 * MIB,
        "tmpfs": 256 * MIB,
        "rounding1024EntriesAt4KiB": 1024 * 4096,
        "namespace1024EntriesAt8KiB": 1024 * 8192,
        "additionalReserve": MIB,
    }
    retained = {
        "originalOtherWorking": 13730880848,
        "oldUntrustedIndex": 8783028224,
        "runtimeImage": 191505175,
        "buildClosureReservation": 14 * GIB,
        "earlierSmallOutputsIncludingSample": GIB,
    }
    memory_mib = {
        "libosmiumQueuesDecompression": 512,
        "pythonRuntime": 256,
        "writerSnapshotsCopies": 256,
        "nativeSemanticMetadataFrames": 128,
        "traceWitnessSelection": 64,
        "directoriesCatalogsCache": 64,
        "logsMetrics": 64,
    }
    road_occurrences = 128 * 1024
    spread = sum(selected_blocks) + 128
    witness_ids = road_occurrences + sum(selected_blocks) + 1024
    # local:4 shard reads; spread:8*4; road:2chunks*3*8+8 first-format reads.
    lookup_shard_multiples = 4 + 32 + 56
    # Format checks once per cohort plus pessimistic decode of every block per batch.
    lookup_rows = 3 * sum(selected_rows) + 3 * (1 + sum(selected_blocks) + 2 * sum(selected_blocks)) * ROWS
    answer = {
        "scope": "Proposal arithmetic, not a national measurement or execution admission",
        "countsPerPass": COUNTS,
        "objectsPerPass": sum(COUNTS.values()),
        "acceptedObjectsAcrossTwoPasses": 2 * sum(COUNTS.values()),
        "blocks": blocks,
        "shards": shards,
        "selectedSourceShardOrdinals": selected,
        "selectedBlocksPerShard": selected_blocks,
        "selectedRowsPerShard": selected_rows,
        "selectedBlocks": sum(selected_blocks),
        "selectedRows": sum(selected_rows),
        "maximumPayloadBytes": payload,
        "maximumShardBytes": shard_bytes,
        "globalDirectoryBytes": 128 + 32 * blocks,
        "maximumMiniIndexBytesIncluding4MiBCatalog": 8 * shard_bytes + 128 + 32 * sum(selected_blocks) + 4 * MIB,
        "writableReservations": writable,
        "writableReservationBytes": sum(writable.values()),
        "writableLimitBytes": GIB,
        "retainedReservations": retained,
        "retainedPlusWritableLimitBytes": sum(retained.values()) + GIB,
        "overallWorkingEnvelopeBytes": 64 * GIB,
        "memoryReservationsMiB": memory_mib,
        "memoryReservationBytes": sum(memory_mib.values()) * MIB,
        "hardMemoryBytes": 4 * GIB,
        "knownPrePostSourceGuardReadBytesTwoPasses": 4 * SOURCE_BYTES,
        "decoderAndOtherIo": "Measure separately; guard reads are not physical or total IO",
        "roadReferenceOccurrencesMax": road_occurrences,
        "spreadQueryOccurrences": spread,
        "sourceWitnessUniqueIdsUpperBound": witness_ids,
        "sourceWitnessTypedRowsBytesUpperBound": 16 * witness_ids,
        "lookupAuthenticatedShardBytesUpperBound": lookup_shard_multiples * shard_bytes,
        "lookupDecodedRowsUpperBound": lookup_rows,
        "lookupDecodedRowsLimit": 256000000,
        "sourceEncodeRowsTwoPasses": 2 * nodes,
        "sourceRoundtripDecodeRowsTwoPasses": 2 * nodes,
        "sourceCodecCallsTwoPasses": 4 * blocks,
        "miniIndexAppendAndReplacementDecodeRowsUpperBound": 3 * sum(selected_rows),
        "checkpointInterval": 65536,
        "checkpointsPerPassIncludingFinal": sum(COUNTS.values()) // 65536 + 1,
        "phaseSeconds": {"eachSourcePass": 3000, "lookup": 300, "otherWorkerWork": 600,
                         "worker": 7200, "host": 7800, "hostBindingHash": 240, "cleanup": 60},
        "prioritySeedHex": hex(SEED),
        "priorityVectors": {str(i): splitmix64(i ^ SEED) for i in (1, 2, 127, 2**31, 2**63 - 1)},
        "nationalMaximumId": None,
        "nationalLogicalIndexBytes": None,
        "illustrative2To40IdBound": full_index_bound(nodes, 2**40 - 1),
        "fullSigned63IdBound": full_index_bound(nodes, 2**63 - 1),
        "fullImportAdmitted": False,
        "nationalExecutionThisStage": False,
    }
    assert blocks == 392146 and shards == 766
    assert selected == [0, 109, 218, 327, 437, 546, 655, 765]
    assert payload == 69623 and shard_bytes == 35679872
    assert sum(writable.values()) < GIB
    assert answer["maximumMiniIndexBytesIncluding4MiBCatalog"] < 384 * MIB
    assert answer["globalDirectoryBytes"] < 16 * MIB
    assert sum(retained.values()) + GIB < 64 * GIB
    assert sum(memory_mib.values()) * MIB < 4 * GIB
    assert witness_ids < 250000 and 16 * witness_ids < 8 * MIB
    assert lookup_shard_multiples * shard_bytes < 4 * GIB
    assert lookup_rows < 256000000
    assert 3 * sum(selected_rows) < 64000000
    assert 4 * blocks < 2000000
    assert 2 * 3000 + 300 + 600 < 7200
    assert 7200 + 240 + 60 < 7800
    assert 2**31 < answer["acceptedObjectsAcrossTwoPasses"] < 2**32
    assert 2 * sum(COUNTS.values()) * (2 * MIB + 4) < 2**64
    assert answer["illustrative2To40IdBound"]["passes24GiBConditionally"]
    assert not answer["fullSigned63IdBound"]["passes24GiBConditionally"]
    # Published SplitMix64 reference outputs, independent of the selected IDs.
    assert splitmix64(0) == 0xE220A8397B1DCDAF
    assert splitmix64(MASK) == 0xE4D971771B652C20
    return answer


if __name__ == "__main__":
    print(json.dumps(result(), indent=2))
