"""Seal the terminal paid boundary-coverage pilot without model execution."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['boundary-coverage-pilot-v1'] = ('us-osm-boundary-coverage-pilot-v1', 'boundary-coverage-pilot-v1')
    closer.close('boundary-coverage-pilot-v1')
