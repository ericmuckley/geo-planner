"""Reuse terminal host-stage closure for unchanged compact geography."""
import close_osm_car_paid_host_v1 as closer


if __name__=='__main__':
    closer.STAGES['car-geography']=('us-osm-car-geography-v1','car-geography')
    closer.close('car-geography')
