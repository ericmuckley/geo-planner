"""Typed compact partition interface; source/native-node objects are never projected."""
from array import array
import ctypes
import hashlib
import os
from pathlib import Path

from coarse_timing_input import require

FIELDS = ('references', 'totalDegree', 'endpointOccurrences', 'uniqueNodes', 'anchors', 'contractedEdges',
          'primitiveEdges', 'taggedSelectedNodes', 'relationNodeSelectedNodes', 'degreeNotTwoNodes', 'wayEndUniqueNodes',
          'allTaggedNodes', 'internalSplitOccurrences', 'outputBytes', 'anchorsWithoutWayEndsBeforeCycleAndCarRules', 'complete')


class Partitions:
    def __init__(self, path, pin):
        with Path(path).open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin, 'Car partition artifact')
        self.library = ctypes.CDLL(str(Path(path).resolve()))
        abi = self.library.gp_car_partition_abi
        abi.restype = ctypes.c_uint32
        require(abi() == 0x10000, 'Car partition ABI')
        self.run = self.library.gp_car_partition_splits
        paths = ctypes.POINTER(ctypes.c_char_p)
        words = ctypes.POINTER(ctypes.c_uint64)
        self.run.argtypes = [paths, ctypes.c_uint32, paths, ctypes.c_uint32, words, ctypes.c_uint64,
                             ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_char_p,
                             words, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        self.run.restype = ctypes.c_int

    def derive(self, references, tags, relation_nodes, destination, *, reference_count, way_count, tag_count, maximum_splits):
        require(isinstance(relation_nodes, array) and relation_nodes.typecode == 'Q' and relation_nodes.itemsize == 8, 'Car partition typed metadata')
        files = [(ctypes.c_char_p * len(paths))(*(os.fsencode(p) for p in paths)) for paths in (references, tags)]
        nodes = (ctypes.c_uint64 * len(relation_nodes)).from_buffer(relation_nodes)
        receipt = (ctypes.c_uint64 * len(FIELDS))()
        error = ctypes.create_string_buffer(512)
        code = self.run(files[0], len(references), files[1], len(tags), nodes, len(relation_nodes), reference_count, way_count, tag_count, maximum_splits,
                        os.fsencode(destination), receipt, len(receipt), error, len(error))
        require(code == 0 and receipt[-1] == 1, 'Car partition stopped: ' + error.value.decode('ascii'))
        return dict(zip(FIELDS, map(int, receipt)))
