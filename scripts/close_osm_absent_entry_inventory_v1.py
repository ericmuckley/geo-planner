"""Seal terminal captured restriction inventory without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'absent-entry-inventory'
    closer.STAGES[key] = ('us-osm-absent-entry-capture-inventory-v1', key)
    closer.close(key)
