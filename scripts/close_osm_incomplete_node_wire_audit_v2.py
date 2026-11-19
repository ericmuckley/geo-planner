"""Seal the corrected graph-epoch byte audit without replaying it."""
import close_osm_car_paid_host_v1 as closer

if __name__ == '__main__':
    key = 'incomplete-node-wire-audit-v2'
    closer.STAGES[key] = ('us-osm-incomplete-node-wire-audit-v2', key)
    closer.close(key)
