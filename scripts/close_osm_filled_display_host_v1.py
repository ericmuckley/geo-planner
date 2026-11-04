"""Close only the fixed, terminal display host stage without replaying it."""
import close_osm_car_paid_host_v1 as closer

closer.STAGES['filled-display']=('us-osm-car-filled-display-profile-v1','filled-display-profile')

if __name__=='__main__':
    closer.close('filled-display')
