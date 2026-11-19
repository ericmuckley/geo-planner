"""Seal terminal conditional-node metadata inventory; no replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['conditional-node-turns-inventory']=('us-osm-conditional-node-turns-inventory-v1','conditional-node-turns-inventory')
    closer.close('conditional-node-turns-inventory')
