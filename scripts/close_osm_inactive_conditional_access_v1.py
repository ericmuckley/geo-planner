"""Seal terminal fresh endpoint collections; never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['inactive-conditional-access']=('us-osm-inactive-conditional-access-v1','inactive-conditional-access')
    closer.close('inactive-conditional-access')
