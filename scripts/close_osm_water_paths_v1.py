"""Seal terminal water path diagnosis; no producer replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='water-paths'
    closer.STAGES[key]=('us-osm-water-path-diagnostic-v1',key)
    closer.close(key)
