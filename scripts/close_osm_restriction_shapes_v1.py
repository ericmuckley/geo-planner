"""Seal the saved-metadata inventory without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'restriction-shapes'
    closer.STAGES[key] = ('us-osm-restriction-shapes-v1', key)
    closer.close(key)
