"""Reuse terminal host-stage closure for the road-field software profile."""
import close_osm_car_paid_host_v1 as closer


if __name__=='__main__':
    closer.STAGES['road-field']=('us-osm-car-road-field-profile-v1','road-field-profile')
    closer.close('road-field')
