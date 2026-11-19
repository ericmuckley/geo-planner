"""Exact original source-way prefix; later overlays kept rejected rows intact."""
from coarse_osm_car_policy_v2 import POLICY, way_policy

REASONS=(None,'outside-major-profile','vehicle-ferry','access','area-ford-driveway-parking','conditional-or-way-restriction','lane-access','unsupported-oneway','unsupported-speed','directional-access')


def original_way_prefix(tags):
    policy=way_policy(tags);role=POLICY['roles'].index(tags['highway'])
    directions=int(policy.forward is not None)|(int(policy.backward is not None)<<1)
    defaults=int(policy.forward_default)|(int(policy.backward_default)<<1)
    flags=directions|(defaults<<2)|(role<<4)|(REASONS.index(policy.reason)<<8)
    return policy.forward or 0.,policy.backward or 0.,flags
