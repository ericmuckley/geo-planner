"""Seal one terminal fixed-attachment source-policy screen; no replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['passable-node-routes']=('us-osm-passable-node-routes-v1','passable-node-routes')
    closer.close('passable-node-routes')
