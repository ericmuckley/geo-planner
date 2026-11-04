"""Close new entry-candidate access/numerical host results without replay."""
import argparse

import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('access', 'evaluation'))
    stage = parser.parse_args().stage
    name = 'us-osm-car-entry-'+('access-profile' if stage == 'access' else 'evaluation')+'-v1'
    key = 'entry-'+stage
    closer.STAGES[key] = (name, key)
    closer.close(key)
