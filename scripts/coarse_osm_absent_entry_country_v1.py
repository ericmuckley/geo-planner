"""Resolve only missing-member static no-turns from complete typed pre-closure facts.

The unchanged exhaustive auditor must reproduce the frozen native baseline first.
No country node dictionary or source geometry is materialized.
"""
from array import array
from bisect import bisect_left
from pathlib import Path
import shutil
import struct
import time

from coarse_osm_car_packed_audit_v1 import rows
from coarse_osm_entry_resolution_audit_v1 import audit, fixed


def resolve(source, rules, fallback, baseline, output, dimensions, native_counts, *, baseline_post, check=lambda: None):
    source, baseline, output = Path(source), Path(baseline), Path(output)
    began = time.monotonic()
    baseline_audit = audit(source, rules, fallback, baseline, dimensions, native_counts,
                           baseline_post=baseline_post, check=check)
    baseline_seconds = time.monotonic()-began
    way_count, _, pre_count, rule_count, fallback_count = dimensions
    ways = array('Q', (r[0] for r in rows(source, 'ways', struct.Struct('<Q24x'))))
    assert len(ways) == way_count and all(a < b for a, b in zip(ways, ways[1:]))
    counts = array('I', [0])*way_count
    pre = 0
    for way, in rows(source, 'arcs', struct.Struct('<8xI20x')):
        assert way < way_count and pre < pre_count
        counts[way] += 1
        pre += 1
        if pre % 16384 == 0:
            check()
    assert pre == pre_count
    def index(identity):
        at = bisect_left(ways, identity)
        return at if at < way_count and ways[at] == identity else None
    def retained(closed):
        return pre_count-sum(counts[at] for identity in closed if (at := index(identity)) is not None)
    old_closed = {r[0] for r in fixed(baseline/'closures-0000.bin', struct.Struct('<Q'), 200000)}
    initial = {r[0] for r in fixed(fallback, struct.Struct('<Q'), 200000)}
    assert len(initial) == fallback_count and initial <= old_closed
    assert retained(old_closed) == native_counts[-1]
    closed = set(initial)
    decisions = list(fixed(baseline/'decisions.bin', struct.Struct('<QII'), 100000))
    new_decisions, inactive = bytearray(), bytearray()
    masks = {str(i): 0 for i in range(1, 8)}
    missing_outside = missing_empty = resolved = kept_fallback = seen = 0
    for rule, decision in zip(fixed(rules, struct.Struct('<QQQQ'), 100000), decisions, strict=True):
        check()
        identity, *members = rule
        assert decision[0] == identity
        mask = 0
        for bit, member in enumerate(members):
            at = index(member)
            if at is None or counts[at] == 0:
                mask |= 1 << bit
                missing_outside += at is None
                missing_empty += at is not None
        _, status, pair_count = decision
        if status == 1:
            assert mask and pair_count == 0
            inactive.extend(struct.pack('<QB7x', identity, mask))
            masks[str(mask)] += 1
            status = 3
        else:
            assert mask == 0 and status in (0, 2)
            if status == 2:
                closed.update(members)
                kept_fallback += 1
            else:
                resolved += 1
        new_decisions.extend(struct.pack('<QII', identity, status, pair_count))
        seen += 1
    inactive_count = len(inactive)//16
    assert seen == rule_count == len(decisions)
    assert inactive_count == native_counts[2] and resolved == native_counts[1] and kept_fallback == native_counts[3]
    assert closed <= old_closed and initial <= closed
    new_post = retained(closed)
    assert native_counts[-1] <= new_post <= pre_count
    output.mkdir()
    (output/'closures-0000.bin').write_bytes(b''.join(struct.pack('<Q', w) for w in sorted(closed)))
    (output/'decisions.bin').write_bytes(new_decisions)
    (output/'inactive-members.bin').write_bytes(inactive)
    shutil.copyfile(baseline/'entry-pairs-pre.u32', output/'entry-pairs-pre.u32')
    assert (output/'entry-pairs-pre.u32').read_bytes() == (baseline/'entry-pairs-pre.u32').read_bytes()
    check()
    return {'status': 'complete_typed_absent_member_no_turn_resolution', 'baselineAudit': baseline_audit,
            'baselineAuditSeconds': baseline_seconds, 'waysChecked': way_count, 'completePreArcsChecked': pre,
            'rulesChecked': seen, 'retainedEntryRules': resolved, 'inactiveMissingMemberRules': inactive_count,
            'remainingNoJoinFallbackRules': kept_fallback, 'constantFallbackWayIdsRetained': len(initial),
            'previousClosureIds': len(old_closed), 'newClosureIds': len(closed),
            'previousFinalArcs': native_counts[-1], 'newFinalArcs': new_post,
            'entryPairsByteIdentical': True, 'closureSubset': True,
            'allOldAllowedTransitionsRetainedWithUnchangedSourceFacts': True,
            'missingRoleMasks': masks, 'missingMemberOccurrencesOutsideSelectedWays': missing_outside,
            'missingMemberOccurrencesWithNoPreArcs': missing_empty,
            'decisionStatusSemantics': {'0': 'existing entry ban retained', '2': 'no join: old whole-member fallback retained',
                                        '3': 'essential preclosure leg absent: this closure contribution omitted'},
            'secondsIncludingBaselineAndResolution': time.monotonic()-began,
            'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'nativeKernelExecutions': 0,
            'routingQueries': 0, 'sourceCostsOrNodeFlagsChanged': False, 'appActivated': False,
            'scope': 'New closure metadata only. Complete PRE-relation-closure facts and every frozen native baseline decision/pair/closure audited first. All other union contributors/conditional/only/unknown constraints retained. No post-closure presence inference, national node dictionary, graph construction/query/ETA/app or geographic rule.'}
