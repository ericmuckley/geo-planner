"""Conditional policy metadata over the immutable full-source NativeScreen bridge."""
import ctypes

from coarse_osm_topology_source_v1 import NativeScreen
from coarse_timing_input import require

COUNTERS = ('nodes', 'ways', 'relations', 'majorWays', 'oldEligibleWays', 'newEligibleWays', 'newlyEligibleWays', 'oldEligibleWaysExact', 'nodesWithConditional', 'changedNodeFlags', 'oldUnblockedNodes', 'oldUnblockedNodesExact', 'majorWaysWithConditional', 'majorWaysWithSpeedConditional', 'newSpeedConditionalWays', 'newNonCarScopedWays', 'speedConditionalStillExcludedWays', 'oldExcludedConditionalWays', 'changedRecords', 'changedTagUtf8Bytes', 'changedEncodedBytes', 'maximumChangedRecordBytes', 'lastChangedNodeId', 'lastChangedWayId', 'complete', 'reserved25', 'oldBlockedNodes', 'newBlockedNodes', 'taggedNodes', 'signalNodes', 'majorReferences', 'majorIgnoredNonCarKeys', 'oldWayReason0', 'oldWayReason1', 'oldWayReason2', 'oldWayReason3', 'oldWayReason4', 'oldWayReason5', 'oldWayReason6', 'oldWayReason7', 'oldWayReason8', 'oldWayReason9', 'newWayReason0', 'newWayReason1', 'newWayReason2', 'newWayReason3', 'newWayReason4', 'newWayReason5', 'newWayReason6', 'newWayReason7', 'newWayReason8', 'newWayReason9', 'reserved52', 'reserved53', 'reserved54', 'reserved55')


class ConditionalCensus(NativeScreen):
    def __init__(self, path, pin, **options):
        super().__init__(path, pin, **options)
        lib = self.library
        lib.gp_conditional_census_abi.restype = ctypes.c_uint32
        require(lib.gp_conditional_census_abi() == 0x10000, 'Conditional census ABI')
        for previous, name in ((self.frames, 'gp_conditional_census_frames'), (self.pbf, 'gp_conditional_census_pbf')):
            function = getattr(lib, name)
            function.argtypes, function.restype = previous.argtypes, previous.restype
            if name.endswith('frames'):
                self.frames = function
            else:
                self.pbf = function
        lib.gp_conditional_census_begin.argtypes = [ctypes.c_char_p,ctypes.c_uint64,ctypes.c_uint64]
        lib.gp_conditional_census_begin.restype = ctypes.c_int
        lib.gp_conditional_census_finish.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        lib.gp_conditional_census_finish.restype = ctypes.c_int
        lib.gp_conditional_census_release.argtypes = []
        lib.gp_conditional_census_release.restype = None
        self.begun = False

    def begin(self, output, *, output_bytes=48*1048576, record_limit=250000):
        from pathlib import Path
        output=Path(output);require(output.is_absolute() and not output.exists(), 'Fresh absolute metadata output')
        require(type(output_bytes) is int and 0<output_bytes<=48*1048576 and type(record_limit) is int and 0<record_limit<=250000, 'Metadata output bounds')
        require(not self.begun and self.library.gp_conditional_census_begin(str(output).encode(),output_bytes,record_limit) == 0, 'Conditional exclusive census session')
        self.begun = True

    def finish(self):
        require(self.begun and not self.active and self.last is not None and self.last['nativeEof'], 'Conditional source complete before finish')
        values = (ctypes.c_uint64*len(COUNTERS))()
        error = ctypes.create_string_buffer(512)
        code = self.library.gp_conditional_census_finish(values, len(values), error, len(error))
        require(code == 0 and values[24] == 1, 'Conditional census finish: '+error.value.decode('ascii'))
        result = dict(zip(COUNTERS, map(int, values)))
        require({k: result[k+'s'] for k in ('node', 'way', 'relation') if result[k+'s']} == self.last['counts'], 'Water/full-source receipt identity')
        return result

    def release(self):
        require(not self.active, 'Conditional release during active source callback')
        if self.begun:
            self.library.gp_conditional_census_release()
            self.begun = False
