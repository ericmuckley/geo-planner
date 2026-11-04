"""V2 namespaces a complete code-mount recipe; V1 worker/reader stay unchanged."""
import argparse

import run_osm_relation_metadata_v1 as original

original.PREFIX = 'data/coarse-quality/us-osm-car-relation-metadata-v2-'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    raise SystemExit(original.driver(args.plan, args.pin))
