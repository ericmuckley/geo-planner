"""Seal the terminal same-resolution display pilot without replay."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['reused-display-pilot-v1']=('us-osm-reused-display-pilot-v1','reused-display-pilot-v1')
    closer.close('reused-display-pilot-v1')
