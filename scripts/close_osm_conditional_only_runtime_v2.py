"""Close a terminal runtime, endpoint or benchmark stage."""
import argparse

import close_osm_car_paid_host_v1 as closer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('runtime', 'access', 'evaluation', 'evaluation-v2'))
    prefix = 'conditional-only-' + parser.parse_args().stage
    suffix = '' if prefix.endswith('-v2') else '-v1'
    closer.STAGES[prefix] = ('us-osm-' + prefix + suffix, prefix)
    closer.close(prefix)
