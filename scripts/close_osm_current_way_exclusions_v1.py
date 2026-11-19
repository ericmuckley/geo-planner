"""Close the terminal metadata inventory without replaying its producer."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['current-way-exclusions']=('us-osm-current-way-exclusions-v1','current-way-exclusions')
    closer.close('current-way-exclusions')
