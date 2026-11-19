"""Seal terminal fixed-timing access/evaluation without producer replay."""
import argparse
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('access', 'evaluation'))
    suffix = parser.parse_args().stage
    key = 'tagged-timing-'+suffix
    name = 'us-osm-tagged-timing-'+('access-profile' if suffix == 'access' else 'evaluation')+'-v1'
    closer.STAGES[key] = (name, key)
    closer.close(key)
