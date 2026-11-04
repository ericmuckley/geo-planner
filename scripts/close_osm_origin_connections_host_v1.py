"""Reuse terminal host-stage closure for the origin-connection profile."""
import close_osm_car_paid_host_v1 as closer


if __name__=='__main__':
    closer.STAGES['origin-connections']=('us-osm-car-origin-connections-profile-v1','origin-connections-profile')
    closer.close('origin-connections')
