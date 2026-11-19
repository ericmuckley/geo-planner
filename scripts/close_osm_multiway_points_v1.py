"""Seal the point-only multi-road prototype without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'multiway-points'
    closer.STAGES[key] = ('us-osm-multiway-point-profile-v1', key)
    closer.close(key)
