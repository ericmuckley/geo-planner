"""Seal the terminal finer-display candidate without replay."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['finer-reused-display-v1']=('us-osm-finer-reused-display-v1','finer-reused-display-v1')
    closer.close('finer-reused-display-v1')
