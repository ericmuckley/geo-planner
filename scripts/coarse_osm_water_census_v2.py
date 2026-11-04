"""Normalize omitted zero-count types when checking the unchanged native census."""
import ctypes

from coarse_osm_water_census_v1 import COUNTERS, WaterCensus as Previous
from coarse_timing_input import require


class WaterCensus(Previous):
    def finish(self):
        require(self.begun and not self.active and self.last is not None and self.last['nativeEof'], 'Water source complete before finish')
        values = (ctypes.c_uint64*len(COUNTERS))()
        error = ctypes.create_string_buffer(512)
        code = self.library.gp_water_census_finish(values, len(values), error, len(error))
        require(code == 0 and values[26] == 1, 'Water census finish: '+error.value.decode('ascii'))
        result = dict(zip(COUNTERS, map(int, values)))
        require({k: result[k+'s'] for k in ('node', 'way', 'relation') if result[k+'s']} == self.last['counts'], 'Water/full-source nonzero receipt identity')
        return result
