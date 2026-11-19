"""Remove only certified contributors; every prior ban and independent closure survives."""
from dataclasses import asdict

from coarse_osm_conditional_node_inventory_v1 import closure_unions
from coarse_osm_conditional_only_node_v1 import classify, forbidden_exits
from coarse_timing_input import require


def overlay(closing_relations, previous_converted, current_closed, metadata, descriptors, old_pairs, source_arcs):
    require(type(source_arcs) is int and 0 < source_arcs <= 0xffffff, 'Exact bounded source pre-arc profile')
    require(isinstance(previous_converted, set) and isinstance(current_closed, set), 'Explicit prior contributor/current closure sets')
    require(all(type(i) is int and 0 < i < 2**63 for i in previous_converted | current_closed), 'Positive prior native identities')
    original, current = closure_unions(closing_relations, previous_converted)
    require(current == current_closed, 'Entire current closure baseline reproduced')
    contributors = {row['sourceRelation']: {int(w) for w in row['closedWays']} for row in closing_relations}
    require(len(metadata) == len(descriptors) <= 100000, 'Every mandatory candidate retains a certificate')
    require(isinstance(old_pairs, list) and len(old_pairs) <= 1000000 and
            all(isinstance(pair, tuple) and len(pair) == 2 and
                all(type(i) is int and 0 <= i < source_arcs for i in pair) for pair in old_pairs) and
            old_pairs == sorted(set(old_pairs)), 'Complete canonical old pre-arc bans')
    certified, additions, fallback = set(), set(), set()
    previous = 0
    for item, port in zip(metadata, descriptors):
        result = classify(item['source'])
        rule = result['rule']
        require(rule is not None and previous < rule.identity, 'Every mandatory source classifies in strict ID order')
        require({k: str(v) if type(v) is int else v for k, v in asdict(rule).items()} == item['derived'], 'Original mandatory derived source IDs')
        previous = rule.identity
        require(rule.identity not in previous_converted and rule.identity in contributors, 'Distinct current closing source contributor')
        require(contributors[rule.identity] == {rule.from_way, rule.to_way}, 'Only exact original member-way contribution changes')
        for key, value in [('sourceRelationId', rule.identity), ('fromWayId', rule.from_way),
                           ('viaNodeId', rule.via_node), ('toWayId', rule.to_way)]:
            require(port[key] == str(value), 'Exact source/native port identity: ' + key)
        require(port['kind'] == rule.kind, 'Exact mandatory source/native kind')
        incoming, outgoing, target = (port[k] for k in ['incomingPreArcIds', 'allOutgoingPreArcIds', 'toOutgoingPreArcIds'])
        for values in (incoming, outgoing, target):
            require(isinstance(values, list) and len(values) <= 1000000 and
                    all(type(i) is int and 0 <= i < source_arcs for i in values) and
                    values == sorted(set(values)), 'Every complete native port remains canonical')
        require(set(target) <= set(outgoing), 'Target ports remain a subset of complete departures')
        if port['status'] != 'source-ports-supported':
            require(port['forbiddenPreArcPairs'] == [], 'Fallback has no admitted mandatory facts')
            fallback.add(rule.identity)
            continue
        require(incoming and rule.from_way in current_closed, 'Every new ban enters a previously closed source way')
        expected = forbidden_exits(incoming, outgoing, target)
        require(port['forbiddenPreArcPairs'] == [list(pair) for pair in expected], 'Every mandatory ban matches the complete port certificate')
        additions.update(expected)
        certified.add(rule.identity)
    require(len(additions) <= 1000000, 'Bounded new mandatory pre-arc pair union')
    _, remaining = closure_unions(closing_relations, previous_converted | certified)
    require(remaining <= current_closed, 'No independent closure is removed or invented')
    combined = sorted(set(old_pairs) | additions)
    require(len(combined) <= 1000000, 'Bounded complete old/new pre-arc ban union')
    return {'originalClosed': original, 'closed': remaining, 'openedWayIds': sorted(current_closed - remaining),
            'convertedRelations': sorted(certified), 'fallbackRelations': sorted(fallback),
            'mandatoryPairs': sorted(additions), 'entryPairs': combined,
            'newEntryPairs': sorted(additions - set(old_pairs)),
            'allOldAllowedTransitionsPreservedByPreviouslyClosedFromWays': True}
