"""Read-only selected original node tags over the immutable full-source NativeScreen bridge."""
import ctypes

from coarse_osm_topology_source_v1 import NativeScreen
from coarse_timing_input import require

COUNTERS = ('nodes','ways','relations','selectedRecords','tagUtf8Bytes','encodedBytes','maximumRecordBytes','lastSelectedId','requestedNodes','complete','reserved10','reserved11','reserved12','reserved13','reserved14','reserved15')


class SelectedNodeTags(NativeScreen):
    def __init__(self, path, pin, **options):
        super().__init__(path, pin, **options)
        lib = self.library
        lib.gp_selected_node_tags_abi.restype = ctypes.c_uint32
        require(lib.gp_selected_node_tags_abi() == 0x10000, 'Selected node tags census ABI')
        for previous, name in ((self.frames, 'gp_selected_node_tags_frames'), (self.pbf, 'gp_selected_node_tags_pbf')):
            function = getattr(lib, name)
            function.argtypes, function.restype = previous.argtypes, previous.restype
            if name.endswith('frames'):
                self.frames = function
            else:
                self.pbf = function
        lib.gp_selected_node_tags_begin.argtypes = [ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint64]
        lib.gp_selected_node_tags_begin.restype = ctypes.c_int
        lib.gp_selected_node_tags_finish.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        lib.gp_selected_node_tags_finish.restype = ctypes.c_int
        lib.gp_selected_node_tags_release.argtypes = []
        lib.gp_selected_node_tags_release.restype = None
        self.begun = False

    def begin(self, output, selected, *, output_bytes=48*1048576):
        from pathlib import Path
        output=Path(output)
        require(output.is_absolute() and not output.exists(), 'Fresh absolute metadata output')
        require(isinstance(selected,(list,tuple)) and len(selected)<=250000 and all(type(v) is int and 0<v<2**63 and (i==0 or v>selected[i-1]) for i,v in enumerate(selected)), 'Selected native ID order/bound')
        require(type(output_bytes) is int and 0<output_bytes<=48*1048576, 'Metadata output bound')
        values=(ctypes.c_uint64*len(selected))(*selected)
        require(not self.begun and self.library.gp_selected_node_tags_begin(values,len(values),str(output).encode(),output_bytes)==0, 'Selected node exclusive census session')
        self.begun=True

    def finish(self):
        require(self.begun and not self.active and self.last is not None and self.last['nativeEof'], 'Selected node tags source complete before finish')
        values = (ctypes.c_uint64*len(COUNTERS))()
        error = ctypes.create_string_buffer(512)
        code = self.library.gp_selected_node_tags_finish(values, len(values), error, len(error))
        require(code == 0 and values[9] == 1, 'Selected node tags census finish: '+error.value.decode('ascii'))
        result = dict(zip(COUNTERS, map(int, values)))
        require({k: result[k+'s'] for k in ('node', 'way', 'relation') if result[k+'s']} == self.last['counts'], 'Selected/full-source receipt identity')
        return result

    def release(self):
        require(not self.active, 'Selected node tags release during active source callback')
        if self.begun:
            self.library.gp_selected_node_tags_release()
            self.begun = False
