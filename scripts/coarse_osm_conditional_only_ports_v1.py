"""Complete mandatory-turn incidence selection, independently replayed by native-ID joins."""
from bisect import bisect_left, bisect_right

from coarse_osm_conditional_node_ports_v1 import (
    MAX_SELECTED_PORTS, WayIdentities, arc_records, source_maps, way_columns,
)
from coarse_osm_conditional_only_node_v1 import KINDS, forbidden_exits
from coarse_timing_input import require


def validate_rules(fields, rules):
    require(len(rules) <= 100000, 'Only-turn source rule bound')
    require(set(fields) == {'ids', 'anchors', 'ways', 'arcs'} and
            0 < len(fields['anchors']) <= len(fields['ids']) <= 64000000 and
            len(fields['anchors']) <= 0xffffff and 0 < len(fields['ways']) <= 5000000 and
            len(fields['arcs']) <= 0xffffff, 'Complete bounded only-turn source dimensions')
    previous = 0
    for rule in rules:
        require(all(type(v) is int and 0 < v < 2**63 for v in
                    (rule.identity, rule.from_way, rule.via_node, rule.to_way)), 'Exact positive only-turn native IDs')
        require(previous < rule.identity and rule.from_way != rule.to_way and rule.kind in KINDS,
                'Sorted unique mandatory source rules')
        previous = rule.identity


def descriptor(rule, nodes, vertices, ways, flags):
    row = {'sourceRelationId': str(rule.identity), 'fromWayId': str(rule.from_way),
           'viaNodeId': str(rule.via_node), 'toWayId': str(rule.to_way), 'kind': rule.kind,
           'fromWayRow': ways.get(rule.from_way), 'toWayRow': ways.get(rule.to_way),
           'viaSourceNodeIndex': nodes.get(rule.via_node), 'viaAnchor': vertices.get(rule.via_node)}
    if rule.from_way not in ways:
        status = 'from-way-outside-major-facts'
    elif not flags[ways[rule.from_way]] & 3:
        status = 'from-way-base-ineligible'
    elif rule.via_node not in nodes:
        status = 'via-node-not-in-selected-source'
    elif rule.via_node not in vertices:
        status = 'via-node-not-an-anchor'
    else:
        status = None
    if rule.to_way not in ways:
        to_status = 'to-way-outside-major-facts'
    elif not flags[ways[rule.to_way]] & 3:
        to_status = 'to-way-base-ineligible'
    else:
        to_status = 'to-way-base-eligible'
    return row | {'status': status, 'toWayStatus': to_status}


def finish(row, incoming, outgoing):
    all_out = [index for index, _way in outgoing]
    to_out = [index for index, way in outgoing if way == row['toWayRow']]
    status = row['status']
    if status is None:
        if not incoming:
            status = 'no-directed-incoming-source-port'
        elif max(len(incoming), len(all_out), len(to_out)) > 64:
            status = 'source-port-complexity-fallback'
        else:
            status = 'source-ports-supported'
    return row | {'status': status, 'incomingPreArcIds': incoming,
                  'allOutgoingPreArcIds': all_out, 'toOutgoingPreArcIds': to_out,
                  'forbiddenPreArcPairs': [list(pair) for pair in forbidden_exits(incoming, all_out, to_out)]
                  if status == 'source-ports-supported' else []}


def qualify(fields, rules, check=lambda: None):
    validate_rules(fields, rules)
    nodes, vertices, ways, flags, points, end = source_maps(fields, rules, check)
    descriptions = [descriptor(rule, nodes, vertices, ways, flags) for rule in rules]
    incoming = {(r['fromWayRow'], r['viaAnchor']): [] for r in descriptions if r['status'] is None}
    outgoing = {r['viaAnchor']: [] for r in descriptions if r['status'] is None}
    selected = 0
    for index, tail, head, way in arc_records(fields, flags, points, check):
        if (way, head) in incoming:
            incoming[way, head].append(index)
            selected += 1
        # Every outgoing WAY matters, including those outside the candidate member set.
        if tail in outgoing:
            outgoing[tail].append((index, way))
            selected += 1
        require(selected <= MAX_SELECTED_PORTS, 'Complete selected mandatory source port cap')
    rows = [finish(row, incoming.get((row['fromWayRow'], row['viaAnchor']), []),
                   outgoing.get(row['viaAnchor'], []) if row['status'] is None else []) for row in descriptions]
    require(sum(len(row['forbiddenPreArcPairs']) for row in rows) <= MAX_SELECTED_PORTS, 'Complete mandatory pair cap')
    return {'rows': rows, 'allSourceNodeIdsChecked': len(fields['ids']),
            'allSourceAnchorsChecked': len(fields['anchors']), 'allSourceWayRowsChecked': len(fields['ways']),
            'allSourcePreArcsChecked': len(fields['arcs']), 'sourceGeometryReferenceCount': end,
            'selectedSourcePortRows': selected}


def audit(fields, rules, actual, check=lambda: None):
    validate_rules(fields, rules)
    for name, key in [('ids', 'allSourceNodeIdsChecked'), ('anchors', 'allSourceAnchorsChecked'),
                      ('ways', 'allSourceWayRowsChecked'), ('arcs', 'allSourcePreArcsChecked')]:
        require(actual[key] == len(fields[name]), 'Complete independently checked only-turn dimensions')
    identities = WayIdentities(fields['ways'])
    nodes, vertices, ways = {}, {}, {}
    for index, rule in enumerate(rules):
        if index % 256 == 0:
            check()
        at = bisect_left(fields['ids'], rule.via_node)
        if at < len(fields['ids']) and fields['ids'][at] == rule.via_node:
            nodes[rule.via_node] = at
            vertex = bisect_left(fields['anchors'], at)
            if vertex < len(fields['anchors']) and fields['anchors'][vertex] == at:
                vertices[rule.via_node] = vertex
        for identity in (rule.from_way, rule.to_way):
            at = bisect_left(identities, identity)
            if at < len(identities) and identities[at] == identity:
                ways[identity] = at
    _, flags, points, end = way_columns(fields['ways'], set(ways), check)
    descriptions = [descriptor(rule, nodes, vertices, ways, flags) for rule in rules]
    keys = sorted({(r['fromWayRow'], r['viaAnchor']) for r in descriptions if r['status'] is None})
    exits = sorted({r['viaAnchor'] for r in descriptions if r['status'] is None})
    incoming, outgoing = [], []
    for index, tail, head, way in arc_records(fields, flags, points, check):
        key = (way, head)
        at = bisect_left(keys, key)
        if at < len(keys) and keys[at] == key:
            incoming.append((*key, index))
        at = bisect_left(exits, tail)
        if at < len(exits) and exits[at] == tail:
            outgoing.append((tail, index, way))
        require(len(incoming) + len(outgoing) <= MAX_SELECTED_PORTS, 'Independent mandatory tuple cap')
    incoming.sort()
    outgoing.sort()
    expected = []
    for row in descriptions:
        if row['status'] is None:
            key = (row['fromWayRow'], row['viaAnchor'])
            entries = [p[2] for p in incoming[bisect_left(incoming, (*key, 0)):bisect_right(incoming, (*key, 0xffffff))]]
            via = row['viaAnchor']
            departures = [(p[1], p[2]) for p in outgoing[
                bisect_left(outgoing, (via, 0, 0)):bisect_right(outgoing, (via, 0xffffff, 0xffffffff))]]
        else:
            entries, departures = [], []
        value = finish(row, entries, departures)
        if value['status'] == 'source-ports-supported':
            # Reconstruct bans directly from actual source way columns, independently of the projection helper.
            bans = [[a, b] for a in entries for b, way in departures if way != row['toWayRow']]
            require(value['forbiddenPreArcPairs'] == bans, 'Every mandatory ban matches native source way membership')
        expected.append(value)
    require(actual['rows'] == expected and actual['sourceGeometryReferenceCount'] == end,
            'Every complete incoming/all-outgoing/to-port descriptor independently replays')
    require(actual['selectedSourcePortRows'] == len(incoming) + len(outgoing), 'Every selected mandatory incidence counted')
    require(sum(len(row['forbiddenPreArcPairs']) for row in expected) <= MAX_SELECTED_PORTS, 'Independent complete mandatory pair cap')
    return {'allCandidateSourceDescriptorsIndependentlyReplayed': len(expected),
            'secondSourcePreArcsChecked': len(fields['arcs']),
            'independentSelectedSourcePortRows': len(incoming) + len(outgoing),
            'supportedRules': sum(row['status'] == 'source-ports-supported' for row in expected),
            'supportedRulesWithoutToPorts': sum(row['status'] == 'source-ports-supported' and not row['toOutgoingPreArcIds'] for row in expected),
            'forbiddenPreArcPairsIncludingOverlaps': sum(len(row['forbiddenPreArcPairs']) for row in expected),
            'sourceOrGraphChanged': False}
