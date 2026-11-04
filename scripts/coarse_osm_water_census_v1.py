"""Water metadata counters over the immutable full-source NativeScreen bridge."""
import ctypes

from coarse_osm_topology_source_v1 import NativeScreen
from coarse_timing_input import require

COUNTERS = ('nodes', 'ways', 'relations', 'waterWays', 'waterWayReferences', 'closedWaterWays', 'openWaterWays',
            'waterRelations', 'waterWayMembers', 'waterNodeMembers', 'waterRelationMembers', 'outerWayMembers',
            'innerWayMembers', 'otherRoleWayMembers', 'selectedEncodedBytes', 'maximumWaterWayReferences',
            'maximumWaterRelationMembers', 'selectedTagUtf8Bytes', 'naturalWaterFeatures', 'riverbankFeatures',
            'reservoirLanduseFeatures', 'multipolygonWaterRelations', 'otherTypeWaterRelations', 'waterWaysAlsoHighways',
            'lastWaterWayId', 'lastWaterRelationId', 'complete', 'reserved27',
            'lakeFeatures', 'reservoirFeatures', 'riverFeatures', 'pondFeatures', 'basinFeatures', 'canalFeatures',
            'lagoonFeatures', 'otherWaterSubtypeFeatures', 'shortClosedWaterWays', 'reserved37', 'reserved38', 'reserved39')


class WaterCensus(NativeScreen):
    def __init__(self, path, pin, **options):
        super().__init__(path, pin, **options)
        lib = self.library
        lib.gp_water_census_abi.restype = ctypes.c_uint32
        require(lib.gp_water_census_abi() == 0x10000, 'Water census ABI')
        for previous, name in ((self.frames, 'gp_water_census_frames'), (self.pbf, 'gp_water_census_pbf')):
            function = getattr(lib, name)
            function.argtypes, function.restype = previous.argtypes, previous.restype
            if name.endswith('frames'):
                self.frames = function
            else:
                self.pbf = function
        lib.gp_water_census_begin.argtypes = []
        lib.gp_water_census_begin.restype = ctypes.c_int
        lib.gp_water_census_finish.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        lib.gp_water_census_finish.restype = ctypes.c_int
        lib.gp_water_census_release.argtypes = []
        lib.gp_water_census_release.restype = None
        self.begun = False

    def begin(self):
        require(not self.begun and self.library.gp_water_census_begin() == 0, 'Water exclusive census session')
        self.begun = True

    def finish(self):
        require(self.begun and not self.active and self.last is not None and self.last['nativeEof'], 'Water source complete before finish')
        values = (ctypes.c_uint64*len(COUNTERS))()
        error = ctypes.create_string_buffer(512)
        code = self.library.gp_water_census_finish(values, len(values), error, len(error))
        require(code == 0 and values[26] == 1, 'Water census finish: '+error.value.decode('ascii'))
        result = dict(zip(COUNTERS, map(int, values)))
        require({k: result[k+'s'] for k in ('node', 'way', 'relation')} == self.last['counts'], 'Water/full-source receipt identity')
        return result

    def release(self):
        require(not self.active, 'Water release during active source callback')
        if self.begun:
            self.library.gp_water_census_release()
            self.begun = False
