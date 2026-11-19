"""A mandatory rule with no represented source approach has no modeled exit to constrain."""
from coarse_osm_conditional_node_inventory_v1 import closure_unions
from coarse_osm_conditional_only_overlay_v1 import overlay as represented_overlay
from coarse_osm_conditional_only_ports_v1 import audit as audit_ports
from coarse_timing_input import require

INACTIVE_FROM = frozenset({'from-way-outside-major-facts', 'from-way-base-ineligible',
                           'no-directed-incoming-source-port'})
POLICY = {
    'id': 'fixed-profile-inactive-conditional-only-from-v1',
    'scope': 'Same qualified three-kind all-state mandatory envelope. No eligible directed incoming from-way port in the COMPLETE fixed pre-closure profile means no represented approach can trigger this rule. Never infer source access, real road absence or local-surrogate permission.',
    'inactiveStatuses': sorted(INACTIVE_FROM),
    'preserved': 'Every represented mandatory ban and independent contributor remains. Missing TO ports still forbids all other outgoing exits; missing/unknown via, nonanchor, complexity and other fallback stay. No post-closure absence inference.',
    'certificate': 'Fresh independent native-ID/whole-way/complete-prearc audit on the identical source profile. Any profile/eligibility/prearc change invalidates and requires recomputation.',
    'unchanged': 'Source prices/flags/physical membership, opaque conditions, every original accuracy/source/shore/transfer/166/app gate; no fit/place/coordinate/region exception or app activation.'
}


def effects(descriptors):
    represented, inactive, fallback = set(), set(), set()
    previous = 0
    for row in descriptors:
        identity = int(row['sourceRelationId'])
        require(previous < identity, 'Every mandatory effect retains a unique source identity')
        previous = identity
        status = row['status']
        if status == 'source-ports-supported':
            require(row['incomingPreArcIds'], 'Represented mandatory rule needs an incoming approach')
            represented.add(identity)
        elif status in INACTIVE_FROM:
            require(not row['incomingPreArcIds'] and row['forbiddenPreArcPairs'] == [], 'No incoming mandatory approach or represented ban')
            if status == 'from-way-outside-major-facts':
                require(row['fromWayRow'] is None, 'Absent from-way in complete fixed profile')
            elif status == 'from-way-base-ineligible':
                require(type(row['fromWayRow']) is int and row['fromWayRow'] >= 0, 'Known base-ineligible from-way')
            else:
                require(all(type(row[key]) is int and row[key] >= 0 for key in
                            ['fromWayRow', 'viaSourceNodeIndex', 'viaAnchor']), 'Negative incoming proof needs a known source junction')
            inactive.add(identity)
        else:
            fallback.add(identity)
    return {'represented': represented, 'inactive': inactive, 'fallback': fallback}


def audit_effects(fields, rules, descriptors, check=lambda: None):
    proof = audit_ports(fields, rules, descriptors, check)
    classified = effects(descriptors['rows'])
    return proof | {'representedRules': len(classified['represented']), 'inactiveFromRules': len(classified['inactive']),
                    'remainingFallbackRules': len(classified['fallback']),
                    'scope': 'Exact complete fixed pre-arc profile only; not source access, local-surrogate behavior or another profile.'}


def overlay(closing_relations, previous_converted, current_closed, metadata, descriptors, old_pairs, source_arcs):
    # The sealed base checks every original source/derived/port identity and all old constraints.
    result = represented_overlay(closing_relations, previous_converted, current_closed, metadata, descriptors, old_pairs, source_arcs)
    classified = effects(descriptors)
    require(set(result['convertedRelations']) == classified['represented'], 'Every represented mandatory constraint unchanged')
    converted = classified['represented'] | classified['inactive']
    _, closed = closure_unions(closing_relations, previous_converted | converted)
    require(closed <= result['closed'], 'Only certified zero-incoming contributors additionally leave fallback')
    return result | {'closed': closed, 'openedWayIds': sorted(current_closed - closed),
                     'convertedRelations': sorted(converted), 'inactiveRelations': sorted(classified['inactive']),
                     'representedRelations': sorted(classified['represented']),
                     'fallbackRelations': sorted(classified['fallback']), 'fixedProfileCertificateRequired': True}
