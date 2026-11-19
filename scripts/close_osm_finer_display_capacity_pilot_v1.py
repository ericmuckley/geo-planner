"""Seal the terminal finer-grid capacity pilot without replay."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['finer-display-capacity-pilot-v1']=('us-osm-finer-display-capacity-pilot-v1','finer-display-capacity-pilot-v1')
    closer.close('finer-display-capacity-pilot-v1')
