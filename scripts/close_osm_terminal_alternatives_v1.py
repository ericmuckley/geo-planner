"""Seal the terminal-choice host prototype without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'terminal-alternatives'
    closer.STAGES[key] = ('us-osm-terminal-alternatives-profile-v1', key)
    closer.close(key)
