"""Reuse terminal host-stage closure for the saved shoreline diagnostic."""
import close_osm_car_paid_host_v1 as closer


if __name__=='__main__':
    closer.STAGES['origin-shores']=('us-osm-car-origin-shore-screen-v1','origin-shore-screen')
    closer.close('origin-shores')
