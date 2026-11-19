"""Use the qualified spatial and geometry worker with the new graph's inputs."""
import argparse

import run_osm_inactive_conditional_derived_v1 as derived


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('pin')
    args = parser.parse_args()
    derived.PREFIX = 'data/coarse-quality/us-osm-conditional-only-derived-'
    raise SystemExit(derived.driver(args.recipe, args.pin))
