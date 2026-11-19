"""Seal the captured explicit-lane graph experiment without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='explicit-lanes-graph-capture'
    closer.STAGES[key]=('us-osm-explicit-lanes-graph-capture-v1',key)
    closer.close(key)
