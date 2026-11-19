"""Seal the read-only flag-lineage review without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='explicit-lane-flag-lineage'
    closer.STAGES[key]=('us-osm-explicit-lane-flag-lineage-v1',key)
    closer.close(key)
