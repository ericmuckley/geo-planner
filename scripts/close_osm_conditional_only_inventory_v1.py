"""Seal the terminal cached only-turn metadata inventory without replay."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    closer.STAGES['conditional-only-inventory-v1'] = ('us-osm-conditional-only-inventory-v1', 'conditional-only-inventory-v1')
    closer.close('conditional-only-inventory-v1')
