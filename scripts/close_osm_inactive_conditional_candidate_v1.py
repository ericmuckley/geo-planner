"""Seal terminal full source-policy candidate; never replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    closer.STAGES['inactive-conditional-evaluation-v1']=('us-osm-inactive-conditional-evaluation-v1','inactive-conditional-evaluation-v1')
    closer.close('inactive-conditional-evaluation-v1')
