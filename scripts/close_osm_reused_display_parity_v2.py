"""Seal the terminal all-origin same-resolution display parity without replay."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['reused-display-parity-v2']=('us-osm-reused-display-parity-v2','reused-display-parity-v2')
    closer.close('reused-display-parity-v2')
