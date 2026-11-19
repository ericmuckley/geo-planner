"""Seal terminal full source-policy candidate; never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['incomplete-node-evaluation']=('us-osm-incomplete-node-evaluation-v1','incomplete-node-evaluation')
    closer.close('incomplete-node-evaluation')
