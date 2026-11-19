"""Seal a terminal captured turn-context experiment; never replay its producer."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'context-turns-capture'
    closer.STAGES[key] = ('us-osm-context-turns-capture-v1', key)
    closer.close(key)
