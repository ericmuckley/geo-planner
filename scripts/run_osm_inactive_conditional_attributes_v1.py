"""Bind the qualified source-attribute worker to a fresh graph epoch."""
import argparse

import run_osm_incomplete_node_attributes_v2 as runner

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('pin')
    args = parser.parse_args()
    runner.PREFIX = 'data/coarse-quality/us-osm-inactive-conditional-attributes-'
    raise SystemExit(runner.driver(args.recipe, args.pin))
