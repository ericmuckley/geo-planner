"""Seal the point-only context prototype without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'context-points'
    closer.STAGES[key] = ('us-osm-context-point-profile-v1', key)
    closer.close(key)
