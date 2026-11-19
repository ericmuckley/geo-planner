"""Seal all-endpoint saved-map geography observations without rerendering."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'tagged-timing-shading'
    closer.STAGES[key] = ('us-osm-tagged-timing-shading-diagnostic-v1', key)
    closer.close(key)
