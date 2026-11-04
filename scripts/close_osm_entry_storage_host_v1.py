"""Seal a terminal candidate codec or independent byte-audit host stage."""
import argparse

import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('core', 'geometry', 'audit-core', 'audit-geometry'))
    stage = parser.parse_args().stage
    key = 'entry-codec-'+stage
    closer.STAGES[key] = ('us-osm-car-'+key+'-v1', key)
    closer.close(key)
