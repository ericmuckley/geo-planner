"""Close terminal captured conditional-tag census; no producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='conditional-scope-capture'
    closer.STAGES[key]=('us-osm-car-conditional-scope-capture-v1',key)
    closer.close(key)
