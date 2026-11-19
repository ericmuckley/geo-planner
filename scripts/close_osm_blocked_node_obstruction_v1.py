"""Seal a terminal optimistic obstruction diagnosis without repeating searches."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'blocked-node-obstruction'
    closer.STAGES[key] = ('us-osm-blocked-node-obstruction-v1', key)
    closer.close(key)
