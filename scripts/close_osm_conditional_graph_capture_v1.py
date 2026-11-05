"""Close terminal captured graph experiment without replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='conditional-graph-capture'
    closer.STAGES[key]=('us-osm-car-conditional-graph-capture-v1',key)
    closer.close(key)
