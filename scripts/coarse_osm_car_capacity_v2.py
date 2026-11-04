"""Reuse the sealed whole-source validator; consume native metadata without projections."""
from array import array
import ctypes
import os

from coarse_osm_topology_source_v1 import NativeScreen
from coarse_osm_car_policy_v1 import POLICY
from coarse_osm_car_native_policy_v1 import REASONS
from coarse_timing_input import require

COUNTERS = ('nodes', 'ways', 'relations', 'majorWays', 'majorReferences', 'primitiveEdges', 'partitionSplitsConsumed',
            'lineageSegmentsIncludingZero', 'zeroNativeLinks', 'nonzeroLineageSegments', 'preClosureArcs', 'postLocatableClosureArcs',
            'unsupportedRelations', 'unsupportedWayMemberOccurrences', 'uniqueUnsupportedMemberWays', 'selectedMemberWays',
            'supportedViaNodeRules', 'nonCarRelations', 'unrelatedRelations', 'unlocatableRestrictions', 'nodeOnlyClosureRelations',
            'eligibleWaysBeforeClosures', 'eligibleDirectionSlotsBeforeClosures', 'defaultSpeedDirectionSlotsBeforeClosures',
            'allTaggedNodes', 'allSignalNodes', 'allBlockedNodes', 'reserved', 'wayFactRows', 'wayFactBytes', 'maximumNativeNodeId', 'complete')


class Capacity(NativeScreen):
    def __init__(self, path, pin, **options):
        super().__init__(path, pin, **options)
        library = self.library
        library.gp_car_capacity_abi.restype = ctypes.c_uint32
        require(library.gp_car_capacity_abi() == 0x10000, 'Car capacity ABI')
        for previous, name in ((self.frames, 'gp_car_capacity_frames'), (self.pbf, 'gp_car_capacity_pbf')):
            function = getattr(library, name)
            function.argtypes = previous.argtypes
            function.restype = previous.restype
            if name.endswith('frames'):
                self.frames = function
            else:
                self.pbf = function
        self.begin_native = library.gp_car_capacity_begin
        self.begin_native.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint64, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
        self.begin_native.restype = ctypes.c_int
        self.finish_native = library.gp_car_capacity_finish
        self.finish_native.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        self.finish_native.restype = ctypes.c_int
        library.gp_car_capacity_release.argtypes = []
        library.gp_car_capacity_release.restype = None
        self.begun = False

    def begin(self, splits, maximum_node_id, destination):
        require(not self.begun and isinstance(splits, array) and splits.typecode == 'Q' and splits.itemsize == 8 and len(splits) <= 8000000, 'Car capacity typed partition input')
        require(type(maximum_node_id) is int and 0 < maximum_node_id <= 14319708500, 'Car capacity presence bound')
        words = (ctypes.c_uint64 * len(splits)).from_buffer(splits)
        error = ctypes.create_string_buffer(512)
        code = self.begin_native(words, len(splits), maximum_node_id, os.fsencode(destination), error, len(error))
        require(code == 0, 'Car capacity begin: ' + error.value.decode('ascii'))
        self.begun = True

    def finish(self):
        require(self.begun and not self.active and self.last is not None and self.last['nativeEof'], 'Car capacity complete source required')
        words = (ctypes.c_uint64 * 64)()
        error = ctypes.create_string_buffer(512)
        code = self.finish_native(words, len(words), error, len(error))
        require(code == 0 and words[31] == 1, 'Car capacity finish: ' + error.value.decode('ascii'))
        result = dict(zip(COUNTERS, map(int, words[:32])))
        require({kind: result[kind+'s'] for kind in ('node', 'way', 'relation')} == {kind: self.last['counts'].get(kind, 0) for kind in ('node', 'way', 'relation')}, 'Car capacity/source receipt counts')
        result['wayReasons'] = {str(reason or 'eligible'): int(words[32+i]) for i, reason in enumerate(REASONS)}
        result['preClosureArcsByRole'] = dict(zip(POLICY['roles'], map(int, words[42:52])))
        result['postLocatableClosureArcsByRole'] = dict(zip(POLICY['roles'], map(int, words[52:62])))
        result['eligibleWaysAfterLocatableClosures'] = int(words[62])
        result['preClosureDefaultSpeedArcs'] = int(words[63])
        result['policyFullyLocatable'] = result['unlocatableRestrictions'] == 0
        return result

    def release(self):
        require(not self.active, 'Car capacity release during source callback')
        if self.begun:
            self.library.gp_car_capacity_release()
            self.begun = False
