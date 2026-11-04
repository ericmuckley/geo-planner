"""Versioned handling of source restrictions with no direct road/node members."""
from coarse_osm_car_policy_v1 import POLICY as LEGACY_POLICY
from coarse_osm_car_policy_v1 import node_policy, restriction_policy as legacy_restriction, way_policy
from coarse_timing_input import PilotError

POLICY = LEGACY_POLICY | {
    'id': 'native-road-only-static-car-prototype-v2',
    'invalidUnlocatableRestrictions': 'Retain full source record and count as invalid-unlocatable; no inferred road closure or nested-relation expansion. Every record with a direct node/way member retains V1 handling.',
}


def restriction_policy(element):
    try:
        return legacy_restriction(element)
    except PilotError as error:
        members = element.get('members', [])
        if str(error) != 'Car prototype cannot locate unsupported restriction' or any(m['type'] in ('node', 'way') for m in members):
            raise
        return {'id': element['id'], 'memberWays': [], 'memberNodes': [],
                'sourceTags': element['tags'], 'sourceMembers': members,
                'status': 'invalid-unlocatable', 'reason': 'unlocatable-source-record'}
