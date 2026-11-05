"""Close terminal mask CPU profile without producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='water-mask-cpu-profile'
    closer.STAGES[key]=('us-osm-water-mask-cpu-profile-v1',key)
    closer.close(key)
