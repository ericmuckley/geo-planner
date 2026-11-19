"""Seal one terminal context-wire host stage, without replaying a producer."""
import argparse
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('pack', 'audit'))
    operation = parser.parse_args().operation
    key = 'context-wire'+('-audit' if operation == 'audit' else '')
    closer.STAGES[key] = ('us-osm-'+key+'-v1', key)
    closer.close(key)
