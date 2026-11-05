"""Close terminal country-certified mask profile, no producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='water-mask-country-profile'
    closer.STAGES[key]=('us-osm-water-mask-country-profile-v1',key)
    closer.close(key)
