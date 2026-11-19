"""Seal the terminal-choice host prototype without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'terminal-alternatives-v2'
    closer.STAGES[key] = ('us-osm-terminal-alternatives-profile-v2', key)
    closer.close(key)
