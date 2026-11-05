"""Close terminal captured static-speed census without producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='conditional-speed-capture'
    closer.STAGES[key]=('us-osm-car-conditional-speed-capture-v1',key)
    closer.close(key)
