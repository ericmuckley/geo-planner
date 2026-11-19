"""Seal captured explicit-lane stages without replaying them."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='explicit-lanes-capture'
    closer.STAGES[key]=('us-osm-explicit-lanes-capture-v1',key)
    closer.close(key)
