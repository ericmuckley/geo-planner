"""Use the unchanged history worker with the new graph's static-entry union."""
import argparse

import run_osm_inactive_conditional_context_v1 as context


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('pin')
    args = parser.parse_args()
    context.PREFIX = 'data/coarse-quality/us-osm-conditional-only-context-'
    raise SystemExit(context.driver(args.recipe, args.pin))
