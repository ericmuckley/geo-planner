"""Seal the terminal host packet profile; no producer or Docker replay."""
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    key='water-geography-profile'
    closer.STAGES[key]=('us-osm-water-geography-profile-v1',key)
    closer.close(key)
