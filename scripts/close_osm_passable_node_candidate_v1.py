"""Seal terminal full source-policy candidate; never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['passable-node-evaluation']=('us-osm-passable-node-evaluation-v1','passable-node-evaluation')
    closer.close('passable-node-evaluation')
