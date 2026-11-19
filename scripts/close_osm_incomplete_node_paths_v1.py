"""Seal the terminal fixed-timing point-winner diagnostic without replay."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'incomplete-node-paths'
    closer.STAGES[key] = ('us-osm-incomplete-node-path-diagnostic-v1', key)
    closer.close(key)
