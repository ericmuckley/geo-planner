"""Seal terminal host overlay output without replaying its producer."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['passable-node-overlay']=('us-osm-passable-node-overlay-v1','passable-node-overlay')
    closer.close('passable-node-overlay')
