"""Seal terminal fresh endpoint collections; never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['incomplete-node-access']=('us-osm-incomplete-node-access-v1','incomplete-node-access')
    closer.close('incomplete-node-access')
