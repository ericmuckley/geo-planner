"""Seal the metadata-only incomplete-turn inventory without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'inactive-conditional-incomplete-flags'
    closer.STAGES[key] = ('us-osm-inactive-conditional-incomplete-flags-v1', key)
    closer.close(key)
