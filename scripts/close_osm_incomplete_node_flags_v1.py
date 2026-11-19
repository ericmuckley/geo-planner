"""Seal the metadata-only incomplete-turn inventory without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'incomplete-node-flags'
    closer.STAGES[key] = ('us-osm-incomplete-node-flags-v1', key)
    closer.close(key)
