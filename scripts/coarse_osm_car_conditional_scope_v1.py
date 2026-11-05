"""Offline car-policy prototype: scope only explicit non-car conditional keys.

Unknown forms, car/general conditions, lane rules and relations keep the
original conservative handling. This module never mutates source tags.
"""
from coarse_osm_car_policy_v2 import POLICY as BASE_POLICY
from coarse_osm_car_policy_v2 import node_policy as base_node_policy
from coarse_osm_car_policy_v2 import restriction_policy
from coarse_osm_car_policy_v2 import way_policy as base_way_policy

NON_CAR_MODES=frozenset({'foot','bicycle','hgv'})
DIRECTIONS=frozenset({'forward','backward'})
MODE_ATTRIBUTES=frozenset({'maxspeed','oneway'})
POLICY=BASE_POLICY|{
    'id':'native-road-only-static-car-conditional-scope-prototype-v1',
    'conditional':'Retain conservative car/general/unknown conditions; ignore only explicit foot/bicycle/hgv mode keys in the documented access, maxspeed and oneway forms.',
    'conditionalScope':'Only <mode>[:forward|backward]:conditional and maxspeed|oneway:<mode>[:forward|backward]:conditional for foot,bicycle,hgv. No condition evaluation, speed factor, lane/relation or source-anchor change.',
}


def ignored_conditional_key(key):
    if not key.endswith(':conditional'):return False
    parts=key.split(':')[:-1]
    if parts and parts[-1] in DIRECTIONS:parts=parts[:-1]
    return len(parts)==1 and parts[0] in NON_CAR_MODES or len(parts)==2 and parts[0] in MODE_ATTRIBUTES and parts[1] in NON_CAR_MODES


def ignored_keys(tags):
    return tuple(sorted(key for key in tags if ignored_conditional_key(key)))


def scoped_tags(tags):
    ignored=ignored_keys(tags)
    return {key:value for key,value in tags.items() if key not in ignored} if ignored else tags


def way_policy(tags):
    return base_way_policy(scoped_tags(tags))


def node_policy(tags):
    result=base_node_policy(scoped_tags(tags))
    # Even an otherwise irrelevant source tag protects native anchors/reversals.
    return result|{'tagged':bool(tags)}
