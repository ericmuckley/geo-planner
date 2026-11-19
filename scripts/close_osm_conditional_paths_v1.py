"""Seal terminal conditional path diagnosis without producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'conditional-paths'
    closer.STAGES[key] = ('us-osm-conditional-path-diagnostic-v1', key)
    closer.close(key)
