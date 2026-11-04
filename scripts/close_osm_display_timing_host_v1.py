"""Close only the fixed terminal numerical/shading screen without replaying it."""
import close_osm_car_paid_host_v1 as closer

closer.STAGES['display-timing']=('us-osm-car-display-timing-evaluation-v1','display-timing-evaluation')

if __name__=='__main__':
    closer.close('display-timing')
