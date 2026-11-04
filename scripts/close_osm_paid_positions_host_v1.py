"""Reuse the terminal host-stage closer for paid-position software checks."""
import close_osm_car_paid_host_v1 as closer


if __name__=='__main__':
    closer.STAGES['paid-positions']=('us-osm-car-paid-positions-profile-v1','paid-positions-profile')
    closer.close('paid-positions')
