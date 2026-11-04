"""Reachability counterfactuals for the frozen captured-road prototype.

These switches are diagnostics, never routing-policy candidates. They do not
establish that a detour exists outside the captured source area.
"""
from array import array
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3

from coarse_osm_car_policy_v1 import node_policy, restriction_policy, turn_allowed, way_policy
from coarse_timing_input import require

MODES = {
    'baseline': frozenset(),
    'without-unsupported-closures': frozenset({'closures'}),
    'without-supported-turns': frozenset({'turns'}),
    'without-blocked-controls': frozenset({'controls'}),
    'without-direction-limits': frozenset({'directions'}),
    'without-way-exclusions': frozenset({'ways'}),
    'geometry-only': frozenset({'closures', 'turns', 'controls', 'directions', 'ways', 'reversal'}),
}
MAX_SETTLES = 20000000


@dataclass(frozen=True, slots=True)
class Arc:
    tail: int
    head: int
    way: int
    part: int
    direction: int


class Network:
    def __init__(self, identities, flags, policies, rules, closures):
        self.identities = identities
        self.flags = flags
        self.policies = policies
        self.rules = rules
        self.closures = closures
        self.arcs = []
        self.outgoing = [[] for _ in identities]
        self.reverse = {}
        self.work = 0

    def add_way(self, identity, refs):
        for part, (a, b) in enumerate(zip(refs, refs[1:])):
            if a == b:
                continue
            for direction in (1, -1):
                tail, head = (a, b) if direction == 1 else (b, a)
                index = len(self.arcs)
                self.arcs.append(Arc(tail, head, identity, part, direction))
                self.outgoing[tail].append(index)
                self.reverse[identity, part, direction] = index
        require(len(self.arcs) <= 1000000, 'Reachability arc cap')

    def allowed(self, index, relax):
        arc = self.arcs[index]
        policy = self.policies[arc.way]
        excluded = policy.reason is not None
        if excluded and not ('ways' in relax or 'directions' in relax and policy.reason == 'directional-access'):
            return False
        if arc.way in self.closures and 'closures' not in relax:
            return False
        return ('ways' in relax and excluded or 'directions' in relax or
                (policy.forward if arc.direction == 1 else policy.backward) is not None)

    def transition(self, before, after, relax):
        a, b = self.arcs[before], self.arcs[after]
        flag = self.flags[a.head]
        reversal = self.reverse.get((a.way, a.part, -a.direction)) == after
        if flag & 1 and 'controls' not in relax:
            return False
        if reversal and not flag & 4 and 'reversal' not in relax:
            return False
        return ('turns' in relax or turn_allowed(a.way, b.way, reversal,
                self.rules.get((a.way, self.identities[a.head]), ())))

    def query(self, source, target, mode='baseline', check=lambda: None):
        relax = MODES[mode]
        if source == target:
            return {'reachable': True, 'settled': 0, 'path': [], 'visited': {source}}
        parent = {i: None for i in self.outgoing[source] if self.allowed(i, relax)}
        queue = deque(parent)
        visited = {source}
        settled = 0
        while queue:
            index = queue.popleft()
            arc = self.arcs[index]
            settled += 1
            self.work += 1
            require(self.work <= MAX_SETTLES, 'Reachability total settle cap')
            if settled % 1024 == 0:
                check()
            visited.add(arc.head)
            if arc.head == target:
                path = []
                cursor = index
                while cursor is not None:
                    path.append(cursor)
                    cursor = parent[cursor]
                return {'reachable': True, 'settled': settled, 'path': path[::-1], 'visited': visited}
            for following in self.outgoing[arc.head]:
                if following not in parent and self.allowed(following, relax) and self.transition(index, following, relax):
                    parent[following] = index
                    queue.append(following)
            require(len(parent) <= 1000000, 'Reachability state cap')
        return {'reachable': False, 'settled': settled, 'path': [], 'visited': visited}

    def witness(self, result):
        path = result['path']
        ways = sorted({self.arcs[i].way for i in path})
        require(len(ways) <= 10000, 'Reachability witness way cap')
        excluded = {str(w): self.policies[w].reason for w in ways if self.policies[w].reason}
        closures = {str(w): self.closures[w] for w in ways if w in self.closures}
        directions = sorted({self.arcs[i].way for i in path if not self.allowed(i, frozenset({'closures', 'ways'}))
                             and self.policies[self.arcs[i].way].reason is None})
        controls = sorted({self.identities[self.arcs[i].head] for i in path[:-1] if self.flags[self.arcs[i].head] & 1})
        turns = set()
        for before, after in zip(path, path[1:]):
            if not self.transition(before, after, frozenset({'controls', 'reversal'})):
                arc = self.arcs[before]
                turns.update(r['id'] for r in self.rules.get((arc.way, self.identities[arc.head]), ()))
        return {'primitiveArcCount': len(path), 'sourceWayIds': ways, 'excludedWaysUsed': excluded,
                'unsupportedClosuresUsed': closures, 'disallowedDirectionWaysUsed': directions,
                'blockedControlsCrossed': controls, 'supportedTurnRuleIdsAtViolations': sorted(turns)}


def load_network(db_path, lineage_root, report, check=lambda: None):
    selected = array('I')
    selected.frombytes((lineage_root / 'provenance/selected-nodes.u32').read_bytes())
    db = sqlite3.connect(db_path.as_uri() + '?mode=ro&immutable=1', uri=True)
    db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA cache_size=-16384')
    all_ids = array('q', (row[0] for row in db.execute("SELECT id FROM objects WHERE kind='node' ORDER BY id")))
    require(len(all_ids) == report['captureReceipt']['types']['node'], 'Reachability source node count')
    identities = array('q', (all_ids[i] for i in selected))
    mapping = {identity: i for i, identity in enumerate(identities)}
    flags = bytearray(len(identities))
    xy = array('i')
    xy.frombytes((lineage_root / 'geometry/xy.i32').read_bytes())
    for i, identity in enumerate(identities):
        if i % 4096 == 0:
            check()
        e = json.loads(db.execute("SELECT raw FROM objects WHERE kind='node' AND id=?", (identity,)).fetchone()[0])
        decision = node_policy(e['tags'])
        flags[i] = int(decision['blocked']) | (4 if decision['tagged'] else 0)
        require([round(e['lon'] * 1e7), round(e['lat'] * 1e7)] == list(xy[2*i:2*i+2]), 'Reachability native coordinates')
    rules = defaultdict(list)
    closures = defaultdict(list)
    relation_counts = Counter()
    relation_sources = {}
    for identity, raw in db.execute("SELECT id,raw FROM objects WHERE kind='relation' ORDER BY id"):
        e = json.loads(raw)
        for member in e['members']:
            if member['type'] == 'node' and member['ref'] in mapping:
                flags[mapping[member['ref']]] |= 4
        rule = restriction_policy(e)
        relation_counts[rule['status']] += 1
        if rule['status'] == 'via-node':
            rules[rule['fromWay'], rule['via']].append(rule)
        elif rule['status'] == 'closed-unsupported':
            relation_sources[str(identity)] = {'reason': rule['reason'], 'tags': e['tags'], 'members': e['members']}
            for way in rule['memberWays']:
                closures[way].append(identity)
            if not rule['memberWays']:
                for node in rule['memberNodes']:
                    if node in mapping:
                        flags[mapping[node]] |= 1
    policies, ways, source_tags = {}, {}, {}
    degree = array('I', [0]) * len(identities)
    ends = set()
    for identity, raw in db.execute("SELECT id,raw FROM objects WHERE kind='way' ORDER BY id"):
        e = json.loads(raw)
        if e['tags'].get('highway') not in report['policy']['roles']:
            continue
        refs = [mapping[node] for node in e['nodes']]
        ways[identity] = refs
        policies[identity] = way_policy(e['tags'])
        source_tags[identity] = e['tags']
        ends.update((refs[0], refs[-1]))
        for a, b in zip(refs, refs[1:]):
            degree[a] += 1
            degree[b] += 1
    for i, d in enumerate(degree):
        if d != 2 or i in ends:
            flags[i] |= 4
    db.close()
    require(len(ways) == report['selectedWays'] and len(identities) == report['selectedNativeNodes'], 'Reachability selected source counts')
    network = Network(identities, flags, policies, rules, closures)
    for identity, refs in ways.items():
        network.add_way(identity, refs)
    return network, mapping, xy, ends, source_tags, relation_sources


def diagnose(repo, check=lambda: None):
    car = repo / 'data/coarse-quality/us-osm-car-run-v1'
    lineage = repo / 'data/coarse-quality/us-osm-lineage-run-v1'
    report = json.loads((car / 'report.json').read_bytes())
    database = repo / 'data/coarse-quality/us-osm-disk-capture-run-v1/extract/audit-selected.sqlite'
    capture = json.loads((repo / 'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json').read_bytes())
    pin = capture['roster']['extract/audit-selected.sqlite']
    require(database.stat().st_size == pin['bytes'], 'Reachability SQLite size')
    with database.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin['sha256'], 'Reachability SQLite identity')
    network, mapping, xy, ends, source_tags, relation_sources = load_network(database, lineage, report, check)
    windows = {w['id']: w['bbox'] for w in json.loads((repo / 'docs/evidence/coarse-osm-way-lineage-prototype-2026-11-01/plan-run-v1.json').read_bytes())['windows']}
    cases, counts = [], Counter()
    for ordinal, q in enumerate(report['queries']):
        a, b = (mapping[n] for n in q['sourceNodeIds'])
        result = network.query(a, b, check=check)
        require(result['reachable'] == (q['raw']['costMs'] is not None), 'Reachability frozen baseline mismatch')
        counts['baselineChecks'] += 1
        if result['reachable']:
            continue
        box = windows[q['windowId']]
        outside = [i for i in result['visited'] if not (box[0] <= xy[2*i]/1e7 <= box[2] and box[1] <= xy[2*i+1]/1e7 <= box[3])]
        entry = {'originalDirectionalIndex': ordinal, 'windowId': q['windowId'], 'sourceNodeIds': q['sourceNodeIds'],
                 'baselineSettles': result['settled'], 'baselineReachableNodes': len(result['visited']),
                 'reachableOutsideWindowPoints': len(outside), 'reachableOutsideWindowWayEnds': sum(i in ends for i in outside),
                 'outsideScopeInterpretation': 'Exposure only; existence of a legal missing detour outside this capture remains unproven.', 'counterfactuals': {}}
        for mode in MODES:
            if mode == 'baseline':
                continue
            found = network.query(a, b, mode, check)
            record = {'reachable': found['reachable'], 'settled': found['settled']}
            if found['reachable']:
                record['witness'] = network.witness(found)
                counts['restored:' + mode] += 1
            entry['counterfactuals'][mode] = record
        require(entry['counterfactuals']['geometry-only']['reachable'], 'Reachability original geometric pair no longer connected')
        cases.append(entry)
    require(len(cases) == 14 and counts['baselineChecks'] == 82, 'Reachability original denominator')
    used_relations = {str(r) for c in cases for result in c['counterfactuals'].values() if result['reachable']
                      for values in result['witness']['unsupportedClosuresUsed'].values() for r in values}
    used_ways = {str(w) for c in cases for result in c['counterfactuals'].values() if result['reachable']
                 for w in result['witness']['sourceWayIds'] if str(w) in result['witness']['excludedWaysUsed'] or
                 str(w) in result['witness']['unsupportedClosuresUsed'] or w in result['witness']['disallowedDirectionWaysUsed']}
    return {'status': 'completed_frozen_car_reachability_diagnosis', 'diagnosticOnly': True, 'counts': dict(counts), 'cases': cases,
            'witnessSourceRelations': {r: relation_sources[r] for r in sorted(used_relations)},
            'witnessConstrainedWayTags': {w: source_tags[int(w)] for w in sorted(used_ways)},
            'settles': network.work, 'modes': {k: sorted(v) for k, v in MODES.items()},
            'interpretation': 'Single-constraint removals show sufficient counterfactual changes, not unique causes or valid route corrections. Geometry-only deliberately ignores vehicle permissions. No evidence of a legal outside-capture detour is inferred.',
            'modelChanged': False, 'etaQualified': False, 'networkRequests': 0, 'applicationDbReads': 0, 'sourcePbfReads': 0}
