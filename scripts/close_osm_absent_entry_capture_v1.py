"""Seal terminal captured absent-member graph experiment without producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'absent-entry-graph-capture'
    closer.STAGES[key] = ('us-osm-absent-entry-graph-capture-v1', key)
    closer.close(key)
