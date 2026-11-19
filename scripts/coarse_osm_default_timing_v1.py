"""One published base-default hypothesis; explicit estimates and permissions stay."""
import math

ROLES = ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link')
CURRENT_DEFAULTS = dict(zip(ROLES, (100, 40, 80, 40, 55, 35, 45, 30, 40, 30)))
PUBLISHED_DEFAULTS = dict(zip(ROLES, (100, 60, 85, 60, 65, 50, 60, 50, 50, 40)))
POLICY = {'id': 'published-base-road-defaults-static-estimate-v1',
          'currentDefaultsKph': CURRENT_DEFAULTS, 'proposedDefaultsKph': PUBLISHED_DEFAULTS,
          'explicitEstimatedSpeedRatio': [1, 1],
          'scope': 'ORS v9.10.0 VehicleFlagEncoder base road-class defaults only. Not complete provider/configuration reproduction or legal/observed speeds. Original legal facts, explicit9/10estimates, physical topology, access, direction, restrictions and all other costs unchanged.'}


def estimated_way(row):
    identity, forward, backward, flags, end = row
    assert type(identity) is int and 0 < identity < 2**63
    assert type(flags) is int and 0 <= flags < 2**32
    assert type(end) is int and 0 <= end < 2**32
    role = (flags >> 4) & 15
    assert role < len(ROLES)
    role = ROLES[role]
    speeds = []
    for index, speed in enumerate((forward, backward)):
        assert type(speed) in (int, float) and math.isfinite(speed) and 0 <= speed <= 160
        assert bool(flags & (1 << index)) == (speed > 0)
        default = bool(flags & (1 << (index + 2)))
        if speed and default:
            assert speed == CURRENT_DEFAULTS[role], 'Current default source identity'
            speed = PUBLISHED_DEFAULTS[role]
        speeds.append(speed)
    return identity, *speeds, flags, end


def continuous_path_ticks(components, groups):
    """Keep this frozen witness; do not infer new optima or exact primitive costs."""
    assert all(type(v) is int and v >= 0 for v in components.values())
    assert sum(g['ticks'] for g in groups.values()) == components['roadTravelTicks']
    road = 0.0
    for name, group in groups.items():
        role, source = name.split('/')
        assert role in CURRENT_DEFAULTS and source in ('default', 'tagged')
        ticks = group['ticks']
        assert type(ticks) is int and ticks >= 0
        assert 0 < group['speedMinKph'] <= group['speedMaxKph'] <= 160
        factor = 1.0
        if source == 'default':
            assert group['speedMinKph'] == group['speedMaxKph'] == CURRENT_DEFAULTS[role]
            factor = CURRENT_DEFAULTS[role] / PUBLISHED_DEFAULTS[role]
        road += ticks * factor
    total = sum(components.values()) - components['roadTravelTicks'] + road
    assert math.isfinite(total) and 0 <= total <= sum(components.values())
    return total
