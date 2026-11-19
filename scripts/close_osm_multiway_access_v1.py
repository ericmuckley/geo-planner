"""Seal the new-ID paid access stage without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'multiway-access'
    closer.STAGES[key] = ('us-osm-multiway-access-profile-v1', key)
    closer.close(key)
