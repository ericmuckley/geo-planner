"""Reuse the terminal host-stage closer for the new geometric profile root."""
import close_osm_car_paid_host_v1 as closer


if __name__=='__main__':
    closer.STAGES['geometric-snap']=('us-osm-car-geometric-snap-profile-v1','geometric-snap-profile')
    closer.close('geometric-snap')
