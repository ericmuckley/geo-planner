"""Seal terminal fresh endpoint collections; never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['passable-node-access']=('us-osm-passable-node-access-v1','passable-node-access')
    closer.close('passable-node-access')
