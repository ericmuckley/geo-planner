"""Seal the captured multi-via prototype without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'multiway-entry-capture'
    closer.STAGES[key] = ('us-osm-multiway-entry-capture-v1', key)
    closer.close(key)
