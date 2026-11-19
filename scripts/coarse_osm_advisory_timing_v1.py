"""One source-backed static estimate: cap at an unscoped posted advisory speed."""
import math

from import_roads import speed_kph

POLICY = {'id': 'unscoped-advisory-static-estimate-cap-v1',
          'rule': 'min(existing estimated driving speed, valid unscoped maxspeed:advisory)',
          'scopedAdvisories': 'unchanged if any maxspeed:advisory:* key is present',
          'legalSpeedsPermissionsAndOtherPrices': 'unchanged', 'fittedCoefficient': None}


def estimated_speed(tags, current):
    assert type(current) in (int, float) and math.isfinite(current) and 0 < current <= 160
    if any(key.startswith('maxspeed:advisory:') for key in tags):
        return current, 'scoped-unchanged'
    value = tags.get('maxspeed:advisory')
    if value is None:
        return current, 'missing-unchanged'
    if not isinstance(value, str):
        return current, 'invalid-unchanged'
    try:
        advisory = speed_kph(value, None)
    except ValueError:
        return current, 'invalid-unchanged'
    return min(current, advisory), 'capped' if advisory < current else 'already-slower'
