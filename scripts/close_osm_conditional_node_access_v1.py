"""Seal terminal fresh endpoint collections; never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['conditional-node-access']=('us-osm-conditional-node-access-v1','conditional-node-access')
    closer.close('conditional-node-access')
