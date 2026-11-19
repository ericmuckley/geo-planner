"""Seal terminal source-qualified node wire packing/audit without replay."""
import argparse
import close_osm_car_paid_host_v1 as closer

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=('pack','audit'));operation=parser.parse_args().operation
    prefix='incomplete-node-wire'+('-audit' if operation=='audit' else '')
    closer.STAGES[prefix]=('us-osm-'+prefix+'-v1',prefix)
    closer.close(prefix)
