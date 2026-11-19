"""Seal the terminal mandatory source-fact reconciliation without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['conditional-only-inactive-overlay-v1'] = ('us-osm-conditional-only-inactive-overlay-v1', 'conditional-only-inactive-overlay-v1')
    closer.close('conditional-only-inactive-overlay-v1')
