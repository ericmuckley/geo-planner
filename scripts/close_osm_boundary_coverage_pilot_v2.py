"""Seal the terminal host-pooling-corrected coverage pilot without model execution."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['boundary-coverage-pilot-v2'] = ('us-osm-boundary-coverage-pilot-v2', 'boundary-coverage-pilot-v2')
    closer.close('boundary-coverage-pilot-v2')
