"""Close a terminal runtime, endpoint or benchmark stage."""
import argparse

import close_osm_car_paid_host_v1 as closer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('runtime', 'access', 'evaluation'))
    prefix = 'conditional-only-' + parser.parse_args().stage
    closer.STAGES[prefix] = ('us-osm-' + prefix + '-v1', prefix)
    closer.close(prefix)
