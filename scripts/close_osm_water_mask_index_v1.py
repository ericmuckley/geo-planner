"""Close terminal mask-only index profile without road/source replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='water-mask-index-profile'
    closer.STAGES[key]=('us-osm-water-mask-index-profile-v1',key)
    closer.close(key)
