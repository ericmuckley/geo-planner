"""Seal the captured lane-tag inventory without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key='lane-metadata-capture'
    closer.STAGES[key]=('us-osm-lane-metadata-capture-v1',key)
    closer.close(key)
