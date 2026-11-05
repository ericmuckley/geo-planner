"""Close the terminal index-only water-candidate correction without replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='water-indexed-evaluation'
    closer.STAGES[key]=('us-osm-water-evaluation-v2',key)
    closer.close(key)
