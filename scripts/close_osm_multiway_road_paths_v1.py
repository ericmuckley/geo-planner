"""Seal the terminal road-only diagnosis without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'multiway-road-paths'
    closer.STAGES[key] = ('us-osm-multiway-road-paths-v1', key)
    closer.close(key)
