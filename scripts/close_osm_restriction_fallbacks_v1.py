"""Seal the saved static-fallback inventory without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'restriction-fallbacks'
    closer.STAGES[key] = ('us-osm-restriction-fallbacks-v1', key)
    closer.close(key)
