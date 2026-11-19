"""Inventory complete cached node-only contributions; never change flags or query."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_car_passable_barriers_v1 import graph_node_decision
from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_incomplete_node_restrictions_v1 import POLICY, classify, remaining_contributors
from coarse_timing_input import require


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    began = time.monotonic()
    recipe = repo / args.plan
    require(sha(recipe) == args.pin, 'Incomplete-node inventory recipe binding')
    plan = json.loads(recipe.read_bytes())
    require(plan['output'] == 'data/coarse-quality/us-osm-incomplete-node-inventory-v1', 'Exact fresh inventory namespace')
    require(plan['priorReserveBytes'] + plan['newClosedAllocationBytes'] + plan['metadataScratchReserveBytes']
            + plan['activeCandidateOwnedReserveBytes'] + 67108864 < 72 * 1024**3, 'All closed and active output reservations')
    require(plan['hostControlsPassed'] == 6 and plan['policy'] == POLICY, 'Predeclared source policy and host controls')
    for name, pin in plan['bindings'].items():
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo / name) == pin, 'Readonly bound inventory input: ' + name)
    active = json.loads((repo / plan['activeCandidateRecipe']).read_bytes())
    require(active['maxOwnedBytes'] == plan['activeCandidateOwnedReserveBytes'] == 268435456, 'Entire active candidate output reserved')
    root = repo / plan['output']
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(recipe.read_bytes())

    def check():
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        require(time.monotonic() - began < 120 and rss < 536870912, 'Inventory host deadline/RSS')
        return rss

    def save(name, value):
        raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
        require(len(raw) <= 1048576, 'Small inventory record cap')
        with (root / name).open('xb') as stream:
            stream.write(raw)

    try:
        reasons, kinds = Counter(), Counter()
        contributors = defaultdict(list)
        incomplete, source_records = {}, []
        previous = count = node_only = 0
        with (repo / plan['rawRelations']).open('rb') as stream:
            while line := stream.readline(2097153):
                require(len(line) <= 2097152 and line.endswith(b'\n') and count < 70376, 'Complete bounded original relation input')
                element = json.loads(line)
                require(previous < element['id'], 'Every original relation in unique native order')
                previous = element['id']
                count += 1
                old = restriction_policy(element)
                require(old['status'] == 'closed-unsupported', 'Original unsupported car metadata')
                if not old['memberWays']:
                    node_only += 1
                    for node in old['memberNodes']:
                        contributors[node].append(element['id'])
                proposed = classify(element)
                reasons[proposed['reason']] += 1
                rule = proposed['rule']
                if rule is not None:
                    require(not old['memberWays'] and old['memberNodes'] == [rule.via_node], 'Only the exact source node contribution can change')
                    incomplete[rule.identity] = rule
                    kinds[rule.kind] += 1
                    source_records.append({'source': element, 'derived': asdict(rule)})
                if count % 256 == 0:
                    check()
        require(count == 70376 and node_only == 2551 and len(contributors) == 1833, 'Complete original node-only closure census')
        raw = gzip.decompress((repo / plan['nodeEvidence']).read_bytes())
        require(len(raw) == plan['nodeEvidenceArtifact']['rawBytes'] <= 8388608
                and hashlib.sha256(raw).hexdigest() == plan['nodeEvidenceArtifact']['rawSha256'], 'Complete known original node-tag evidence')
        evidence = json.loads(raw)['nodeEvidence']
        require(len(evidence) == 13776, 'Every original blocked graph node retained')
        affected = []
        old_blocked = new_blocked = relation_nodes = retained_independent = 0
        for identity, row in evidence.items():
            node = int(identity)
            original = row['restrictionContributorIds']
            require(original == contributors.get(node, []), 'Every original selected node contribution independently reconstructed')
            relation_nodes += bool(original)
            remaining = remaining_contributors(node, original, incomplete)
            before = graph_node_decision(row['rawTags'], original)
            after = graph_node_decision(row['rawTags'], remaining)
            require(before['base'] == after['base'] and (not after['blocked'] or before['blocked']), 'Every direct node guard and old open node retained')
            old_blocked += before['blocked']
            new_blocked += after['blocked']
            retained_independent += bool(remaining)
            if before['blocked'] and not after['blocked']:
                require(original and not remaining and not after['base']['blocked'], 'Potential opening has only incomplete contributors and no direct block')
                affected.append({'sourceNodeId': identity, 'removedContributorIds': original,
                                 'remainingContributorIds': remaining, 'rawTags': row['rawTags']})
        require(relation_nodes == 1501 and old_blocked == 8062, 'Complete current passable-node epoch logically reproduced')
        payload = {'incompleteRelations': source_records, 'potentialNodeChanges': affected}
        raw = (json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
        require(len(raw) <= 16777216, 'Bounded complete incomplete-relation inventory')
        packed = gzip.compress(raw, mtime=0)
        with (root / 'incomplete-node-metadata.json.gz').open('xb') as stream:
            stream.write(packed)
        restored = json.loads(gzip.decompress((root / 'incomplete-node-metadata.json.gz').read_bytes()))
        require(restored == payload, 'Every selected source/derived row reopens exactly')
        for row in restored['incompleteRelations']:
            require(asdict(classify(row['source'])['rule']) == row['derived'], 'Every selected original schema independently replays')
        for name, pin in plan['bindings'].items():
            require(sha(repo / name) == pin, 'All source/code evidence unchanged')
        save('report.json', {'status': 'complete_incomplete_node_maneuver_metadata_inventory', 'policy': POLICY,
                            'allRawUnsupportedRelations': count, 'originalNodeOnlyRelations': node_only,
                            'originalNodeOnlyClosureIds': len(contributors), 'selectedIncompleteRelations': len(incomplete),
                            'classificationCounts': dict(reasons), 'selectedKinds': dict(kinds),
                            'allOriginalBlockedNodeTagsReplayed': len(evidence), 'originalRestrictionBlockedGraphNodes': relation_nodes,
                            'currentPassablePolicyBlockedNodes': old_blocked, 'proposedPolicyBlockedNodes': new_blocked,
                            'potentialNewOpenGraphNodes': len(affected), 'nodesRetainingIndependentContributors': retained_independent,
                            'everyDirectNodeGuardRetained': True, 'everyOtherContributorRetained': True,
                            'artifact': {'file': 'incomplete-node-metadata.json.gz', 'bytes': len(packed),
                                         'sha256': hashlib.sha256(packed).hexdigest(), 'rawBytes': len(raw),
                                         'rawSha256': hashlib.sha256(raw).hexdigest()},
                            'hostSecondsIncludingBindingsAllRelationsTagsAndIndependentContributorReplay': time.monotonic() - began,
                            'hostMaximumRssBytes': check(), 'sourcePbfReads': 0, 'routingQueries': 0, 'providerRequests': 0,
                            'applicationDbReads': 0, 'actualNodeFlagsChanged': False, 'nativeOrRuntimeQualified': False, 'appActivated': False,
                            'scope': 'Complete cached raw-relation and original node-tag metadata only. Exact source-schema rule is predeclared and six host controls pass. Reconstruct all original node-only contributors before logically applying only the singleton-via static-incomplete rule; retain all direct guards/independent contributors and qualified passable-barrier policy. Proposed counts are not changed flags, roads, legal-permission/route/accuracy or app admission. Current conditional-junction full candidate is unchanged and its entire256MiBoutput is reserved. Host512MiBRSS/120s/64MiBoutput/72GiBaggregate; not cgroup/CPU/cloud timing. No PBF/provider/applicationDB/graph/model query.'})
    except BaseException as error:
        save('failure.json', {'status': 'incomplete_node_inventory_stopped', 'error': repr(error)})
        raise


if __name__ == '__main__':
    main()
