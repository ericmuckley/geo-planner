"""Draft typed bridge for offline coordinate/lineage/cost facts, never app data."""
from array import array
import ctypes
import os

from coarse_osm_car_native_policy_v1 import REASONS
from coarse_osm_car_policy_v2 import POLICY
from coarse_osm_topology_source_v1 import NativeScreen
from coarse_timing_input import require

COUNTERS = ('nodes', 'ways', 'relations', 'selectedNodes', 'anchors', 'majorWays', 'majorReferences',
            'nonzeroLineageSegments', 'preClosureArcs', 'postClosureArcs', 'preClosureCostOverflows',
            'postClosureCostOverflows', 'supportedViaNodeRules', 'unsupportedRelations',
            'unsupportedWayMemberOccurrences', 'invalidUnlocatableRestrictions', 'selectedCoordinatesSeen',
            'nodeIndexAllocatedBytes', 'geometryReferences', 'geometryBytes', 'arcFactBytes', 'wayFactBytes',
            'maximumPrimitiveMs', 'maximumMacroMs', 'reserved', 'uniqueUnsupportedMemberWays',
            'allTaggedNodes', 'allSignalNodes', 'allBlockedNodes', 'reserved2', 'outputBytes', 'complete')


class CostGraph(NativeScreen):
    def __init__(self, path, pin, **options):
        super().__init__(path, pin, **options)
        library = self.library
        library.gp_car_graph_abi.restype = ctypes.c_uint32
        require(library.gp_car_graph_abi() == 0x10000, 'Cost graph ABI')
        for old, name in ((self.frames, 'gp_car_graph_frames'), (self.pbf, 'gp_car_graph_pbf')):
            function = getattr(library, name);function.argtypes = old.argtypes;function.restype = old.restype
            if name.endswith('frames'):self.frames = function
            else:self.pbf = function
        paths = ctypes.POINTER(ctypes.c_char_p);words = ctypes.POINTER(ctypes.c_uint64)
        self.begin_native = library.gp_car_graph_begin
        self.begin_native.argtypes = [paths, ctypes.c_uint32, paths, ctypes.c_uint32, words, ctypes.c_uint64,
                                     ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64,
                                     ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
        self.begin_native.restype = ctypes.c_int
        self.finish_native = library.gp_car_graph_finish
        self.finish_native.argtypes = [words, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        self.finish_native.restype = ctypes.c_int
        library.gp_car_graph_release.argtypes = [];library.gp_car_graph_release.restype = None
        self.begun = False

    def begin(self, references, tags, relation_nodes, destination, *, reference_count, way_count, tag_count,
              maximum, selected, anchors):
        require(not self.begun and len(references) <= 256 and len(tags) <= 256, 'Cost graph begin/part bound')
        require(isinstance(relation_nodes, array) and relation_nodes.typecode == 'Q' and relation_nodes.itemsize == 8 and len(relation_nodes) <= 67108864, 'Cost graph typed relation nodes')
        values = (reference_count, way_count, tag_count, maximum, selected, anchors)
        require(all(type(n) is int and n >= 0 for n in values) and reference_count <= 509547029 and
                way_count <= reference_count//2 and tag_count <= 1606229364 and 0 < maximum <= 14319708500 and
                anchors <= selected <= 64000000, 'Cost graph finite preparation bounds')
        files = [(ctypes.c_char_p*len(paths))(*(os.fsencode(p) for p in paths)) for paths in (references, tags)]
        nodes = (ctypes.c_uint64*len(relation_nodes)).from_buffer(relation_nodes)
        error = ctypes.create_string_buffer(512)
        code = self.begin_native(files[0], len(references), files[1], len(tags), nodes, len(nodes), reference_count,
                                 way_count, tag_count, maximum, selected, anchors, os.fsencode(destination), error, len(error))
        require(code == 0, 'Cost graph begin: '+error.value.decode('ascii'))
        self.begun = True

    def finish(self):
        require(self.begun and not self.active and self.last is not None and self.last['nativeEof'], 'Cost graph complete source required')
        words = (ctypes.c_uint64*64)();error = ctypes.create_string_buffer(512)
        code = self.finish_native(words, len(words), error, len(error))
        require(code == 0 and words[31] == 1, 'Cost graph finish: '+error.value.decode('ascii'))
        result = dict(zip(COUNTERS, map(int, words[:32])))
        require({kind: result[kind+'s'] for kind in ('node', 'way', 'relation')} ==
                {kind: self.last['counts'].get(kind, 0) for kind in ('node', 'way', 'relation')}, 'Cost graph source type totals')
        result['wayReasons'] = {str(reason or 'eligible'): int(words[32+i]) for i, reason in enumerate(REASONS)}
        result['preClosureArcsByRole'] = dict(zip(POLICY['roles'], map(int, words[42:52])))
        result['postClosureArcsByRole'] = dict(zip(POLICY['roles'], map(int, words[52:62])))
        result['policyId'] = POLICY['id']
        return result

    def release(self):
        require(not self.active, 'Cost graph release during source callback')
        if self.begun:
            self.library.gp_car_graph_release();self.begun = False
