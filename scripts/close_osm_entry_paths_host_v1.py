"""Seal the new candidate's terminal path diagnosis without repeating it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['entry-paths'] = ('us-osm-car-entry-path-diagnostic-v1', 'entry-paths')
    closer.close('entry-paths')
