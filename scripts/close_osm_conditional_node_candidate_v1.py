"""Seal terminal full source-policy candidate; never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['conditional-node-evaluation']=('us-osm-conditional-node-evaluation-v1','conditional-node-evaluation')
    closer.close('conditional-node-evaluation')
