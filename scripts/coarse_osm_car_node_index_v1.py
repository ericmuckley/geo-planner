"""Typed offline node-rank probe. No PBF, coordinate store or Python node map."""
from array import array
import ctypes
import hashlib
from itertools import chain
import os
from pathlib import Path

from coarse_timing_input import require

FIELDS = ('references', 'selectedNodes', 'anchors', 'referenceLookups', 'indexAllocatedBytes',
          'maximumNodeId', 'typedSourceMergePasses', 'complete')


class NativeIndex:
    def __init__(self, path, pin):
        path = Path(path)
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216, 'Index artifact bound')
        with path.open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin, 'Index artifact hash')
        self.library = ctypes.CDLL(str(path.resolve()))
        self.library.gp_car_node_index_abi.restype = ctypes.c_uint32
        require(self.library.gp_car_node_index_abi() == 0x10000, 'Node index ABI')
        words = ctypes.POINTER(ctypes.c_uint64)
        paths = ctypes.POINTER(ctypes.c_char_p)
        self.query = self.library.gp_car_node_index_queries
        self.query.argtypes = [words, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32, ctypes.c_uint64,
                               words, ctypes.c_uint32, words, ctypes.c_char_p, ctypes.c_uint32]
        self.query.restype = ctypes.c_int
        self.probe = self.library.gp_car_node_index_probe
        self.probe.argtypes = [paths, ctypes.c_uint32, paths, ctypes.c_uint32, words, ctypes.c_uint64,
                              ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64,
                              ctypes.c_uint32, ctypes.c_uint32, words, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        self.probe.restype = ctypes.c_int

    def queries(self, ids, anchors, queries, maximum):
        require(len(ids) == len(anchors) and len(ids) <= 2000000 and len(queries) <= 2000000, 'Index test input bound')
        require(type(maximum) is int and 0 < maximum < 2**34, 'Index maximum native ID')
        require(all(type(n) is int and 0 <= n < 2**64 for n in chain(ids, queries)), 'Index unsigned64 input')
        require(all(type(n) is int and n in (0, 1) for n in anchors), 'Index anchor input')
        values = [(ctypes.c_uint64*len(a))(*a) for a in (ids, queries)]
        flags = (ctypes.c_uint8*len(anchors))(*anchors)
        out = (ctypes.c_uint64*len(queries))()
        error = ctypes.create_string_buffer(512)
        code = self.query(values[0], flags, len(ids), maximum, values[1], len(queries), out, error, len(error))
        require(code == 0, 'Node rank query: '+error.value.decode('ascii'))
        return [(value & 0xffffffff, value >> 32) for value in out]

    def run(self, references, tags, relation_nodes, *, reference_count, way_count, tag_count, maximum, selected, anchors):
        require(isinstance(relation_nodes, array) and relation_nodes.typecode == 'Q' and relation_nodes.itemsize == 8, 'Index typed relation IDs')
        require(0 <= reference_count <= 509547029 and 0 <= way_count <= reference_count//2 and 0 <= tag_count <= 1606229364, 'Index expected source counts')
        require(0 <= selected <= 64000000 and 0 <= anchors <= selected and 0 < maximum < 2**34, 'Index expected output counts')
        files = [(ctypes.c_char_p*len(paths))(*(os.fsencode(p) for p in paths)) for paths in (references, tags)]
        nodes = (ctypes.c_uint64*len(relation_nodes)).from_buffer(relation_nodes)
        out = (ctypes.c_uint64*len(FIELDS))()
        error = ctypes.create_string_buffer(512)
        code = self.probe(files[0], len(references), files[1], len(tags), nodes, len(nodes), reference_count,
                          way_count, tag_count, maximum, selected, anchors, out, len(out), error, len(error))
        require(code == 0 and out[-1] == 1, 'Node rank probe: '+error.value.decode('ascii'))
        return dict(zip(FIELDS, map(int, out)))
