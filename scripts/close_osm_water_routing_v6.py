"""Close terminal country-certified water candidate without producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='water-country-evaluation'
    closer.STAGES[key]=('us-osm-water-evaluation-v6',key)
    closer.close(key)
