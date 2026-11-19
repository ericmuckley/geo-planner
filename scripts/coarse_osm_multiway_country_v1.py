"""Typed national metadata only: preserve the complete old closure/entry baseline."""
from array import array
from bisect import bisect_left
from collections import Counter, defaultdict
import json
from pathlib import Path
import struct
import time

from coarse_osm_car_packed_audit_v1 import ARC, rows
from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_entry_resolution_audit_v1 import fixed
from coarse_osm_multiway_entry_v1 import multiway_rule
from coarse_osm_restriction_entry_v1 import entry_restriction

MAX_SELECTED = 400000


def resolve(source, metadata, old_decisions, old_closures, old_pairs, output, dimensions, check=lambda:None):
    began = time.monotonic()
    way_count, vertices, pre_count, old_post, metadata_count, single_count = dimensions
    assert 0 < way_count <= 5000000 and 0 < vertices <= 0xffffff and 0 < pre_count <= 0xffffff
    assert 0 < metadata_count <= 100000 and 0 < single_count <= metadata_count
    identities = array('Q',(r[0] for r in rows(source,'ways',struct.Struct('<Q24x'))))
    assert len(identities) == way_count and all(a < b for a,b in zip(identities,identities[1:]))
    counts = array('I',[0])*way_count
    decisions = {r[0]:r[1:] for r in fixed(old_decisions,struct.Struct('<QII'),100000)}
    assert len(decisions) == single_count and all(status in (0,2,3) for status,_ in decisions.values())
    baseline = {r[0] for r in fixed(old_closures,struct.Struct('<Q'),200000)}
    baseline_pairs = list(fixed(old_pairs,struct.Struct('<II'),200000))
    assert baseline_pairs == sorted(set(baseline_pairs)) and all(max(pair) < pre_count for pair in baseline_pairs)
    rules, constant, baseline_union = [], set(), set()
    all_single = set(); previous = seen = 0
    with Path(metadata).open('rb') as stream:
        for line in stream:
            check()
            assert len(line) <= 2097152 and line.endswith(b'\n')
            element = json.loads(line)
            assert type(element['id']) is int and previous < element['id'] < 2**63
            previous = element['id']; seen += 1; assert seen <= metadata_count
            policy = restriction_policy(element)
            assert policy['status'] == 'closed-unsupported'
            single = entry_restriction(element)
            if single is not None:
                all_single.add(single.identity)
                status,_ = decisions[single.identity]
                if status == 2:
                    constant.update(policy['memberWays']); baseline_union.update(policy['memberWays'])
                continue
            baseline_union.update(policy['memberWays'])
            multi = multiway_rule(element)
            if multi is None:
                constant.update(policy['memberWays'])
            else:
                rules.append(multi)
                assert len(rules) <= 10000
    assert seen == metadata_count and all_single == decisions.keys() and baseline_union == baseline
    selected_ways = {rule.from_way for rule in rules} | {way for rule in rules for way in rule.via_ways}
    selected_indices = {at for identity in selected_ways if (at:=bisect_left(identities,identity)) < way_count and identities[at] == identity}
    selected = defaultdict(list); selected_count = pre = 0
    for tail,head,way,*_ in rows(source,'arcs',ARC):
        assert tail < vertices and head < vertices and way < way_count and pre < pre_count
        counts[way] += 1
        if way in selected_indices:
            selected[identities[way]].append((pre,tail,head))
            selected_count += 1; assert selected_count <= MAX_SELECTED
        pre += 1
        if pre % 65536 == 0: check()
    assert pre == pre_count
    def number(identity):
        at = bisect_left(identities,identity)
        return counts[at] if at < way_count and identities[at] == identity else 0
    def retained(closures):
        return pre_count-sum(number(identity) for identity in closures)
    assert retained(baseline) == old_post
    closed = set(constant); pairs = set(); statuses = []
    resolved = inactive = no_join = 0
    for rule in rules:
        check()
        members = {rule.from_way,*rule.via_ways,rule.to_way}
        if any(number(member) == 0 for member in members):
            status,found = 3,set();inactive += 1
        else:
            exits = defaultdict(list)
            for via in rule.via_ways:
                for index,tail,_ in selected[via]: exits[tail].append(index)
            found = {(index,after) for index,_,head in selected[rule.from_way] for after in exits[head]}
            status = 0 if found else 2
            if found: resolved += 1; pairs.update(found)
            else: no_join += 1;closed.update(members)
        statuses.append((rule.identity,status,len(found)))
        assert len(pairs) <= 200000 and len(closed) <= 200000
    assert closed <= baseline and constant <= closed
    assert all(rule.from_way in baseline and all(v in baseline for v in rule.via_ways) for rule in rules)
    # Independent join formulation/source reread: sort and merge source anchor
    # incidences, rather than trust the constructor's outgoing adjacency map.
    audit_selected = defaultdict(list); audit_counts = array('I',[0])*way_count; audit_pre = 0
    for tail,head,way,*_ in rows(source,'arcs',ARC):
        audit_counts[way] += 1
        if way in selected_indices: audit_selected[identities[way]].append((audit_pre,tail,head))
        audit_pre += 1
        if audit_pre % 65536 == 0: check()
    assert audit_pre == pre_count and audit_counts == counts
    assert sum(map(len,audit_selected.values())) == selected_count
    expected_pairs = set(); expected_closed = set(constant); checked_states = Counter()
    for rule, decision in zip(rules,statuses,strict=True):
        assert decision[0] == rule.identity
        members = {rule.from_way,*rule.via_ways,rule.to_way}
        joined = set()
        absent = any(number(w) == 0 for w in members)
        if not absent:
            incoming = sorted((head,index) for index,_,head in audit_selected[rule.from_way])
            outgoing = sorted((tail,index) for via in rule.via_ways for index,tail,_ in audit_selected[via])
            i=j=0
            while i < len(incoming) and j < len(outgoing):
                if incoming[i][0] < outgoing[j][0]: i += 1;continue
                if incoming[i][0] > outgoing[j][0]: j += 1;continue
                head = incoming[i][0]; ie=i; je=j
                while ie < len(incoming) and incoming[ie][0] == head: ie += 1
                while je < len(outgoing) and outgoing[je][0] == head: je += 1
                joined.update((a,b) for _,a in incoming[i:ie] for _,b in outgoing[j:je]);i=ie;j=je
        expected_status = 3 if absent else 0 if joined else 2
        assert decision[1:] == (expected_status,len(joined))
        checked_states[expected_status] += 1
        if expected_status == 2: expected_closed.update(members)
        expected_pairs.update(joined)
    assert expected_closed == closed and expected_pairs == pairs
    combined = sorted(set(baseline_pairs)|pairs)
    output = Path(output);output.mkdir()
    (output/'closures-0000.bin').write_bytes(b''.join(struct.pack('<Q',w) for w in sorted(closed)))
    for name,values in [('multi-entry-pairs-pre.u32',sorted(pairs)),('entry-pairs-pre.u32',combined)]:
        (output/name).write_bytes(b''.join(struct.pack('<II',*pair) for pair in values))
    (output/'multi-decisions.bin').write_bytes(b''.join(struct.pack('<QII',*row) for row in statuses))
    check()
    return {'status':'complete_multi_via_country_metadata_and_independent_join_audit_passed',
            'waysChecked':way_count,'preArcsCheckedTwice':pre_count,'sourceUnsupportedRelationsChecked':seen,
            'oldSingleViaDecisionsRetained':single_count,'oldClosureUnionReproduced':True,
            'oldEntryPairsRetained':len(baseline_pairs),'newMultiEntryPairs':len(pairs),'combinedEntryPairs':len(combined),
            'multiViaRules':len(rules),'resolvedMultiViaRules':resolved,'inactiveMissingMemberMultiRules':inactive,
            'noJoinMultiFallbackRules':no_join,'oldClosureIds':len(baseline),'newClosureIds':len(closed),
            'oldPostArcs':old_post,'proposedPostArcs':retained(closed),'sourceCostsFlagsOrPreArcsChanged':False,
            'oldAllowedPathsPreservedByClosureSubsetAndNewEntryWaysPreviouslyClosed':True,
            'selectedPreArcRecordsPerAudit':selected_count,'denseWayIdentityAndCountBytes':identities.itemsize*len(identities)+counts.itemsize*len(counts),
            'independentSourceJoinDecisionCounts':dict(checked_states),
            'secondsIncludingBaselineConstructionAndIndependentRereadAudit':time.monotonic()-began,
            'sourcePbfReads':0,'coordinatesRead':0,'routingQueries':0,'appActivated':False,
            'scope':'Complete PRE-closure typed facts and saved raw restrictions. Exact old union/single decisions/entry pairs retained;new multi-way no-turns banfrom->ANYvia,missing essential PRE leg inactive,no-join keeps whole-member fallback. All other contributors preserved. Independent second source pass/sort-merge joins verify every decision/pair/closure. No CSR/spatial/runtime/geometry/ETA/app admission.'}
