"""Reconcile certified mandatory-turn deltas; emit new facts without building a graph."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from analyze_osm_conditional_only_inventory_v1 import derived
from coarse_osm_bulk_pbf import stat_key
from coarse_osm_conditional_node_turns_v2 import classify as previous_classify
from coarse_osm_conditional_only_overlay_v1 import overlay
from coarse_osm_country_screen_v1 import owned_usage
from coarse_timing_input import require

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    recipe = REPO / args.recipe
    require(sha(recipe) == args.pin, 'Mandatory overlay recipe binding')
    plan = json.loads(recipe.read_bytes())
    require(plan['output'] == 'data/coarse-quality/us-osm-conditional-only-overlay-v1', 'Exact mandatory overlay namespace')
    require(plan['priorReserveBytes'] + plan['newClosedAllocationBytes'] + plan['metadataScratchReserveBytes'] + 67108864 < 72 * 1024**3,
            'Mandatory overlay aggregate reservation')
    before = {}
    for name, pin in plan['bindings'].items():
        require(not name.endswith(('.pbf', '/001.bin')) and sha(REPO / name) == pin, 'Mandatory overlay read-only binding: ' + name)
        before[name] = stat_key(REPO / name)
    root = REPO / plan['output']
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(recipe.read_bytes())

    def check():
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        require(time.monotonic() - began < 300 and rss < 536870912 and owned_usage(root)['conservativeAllocatedBytes'] < 67108864,
                'Mandatory overlay host deadline/RSS/owned cap')
        return rss

    def load(name):
        return json.loads((REPO / plan[name]).read_bytes())

    def unpack(name, size, pin):
        with gzip.open(REPO / plan[name], 'rb') as stream:
            raw = stream.read(size + 1)
        require(len(raw) == size and hashlib.sha256(raw).hexdigest() == pin, 'Complete compressed source evidence: ' + name)
        return json.loads(raw)

    def save(name, value):
        raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
        require(len(raw) <= 1048576, 'Mandatory overlay portable metadata cap')
        with (root / name).open('xb') as stream:
            stream.write(raw)
        return {'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    try:
        metadata = load('metadata')['candidates']
        ports = load('ports')['rows']
        require(len(metadata) == len(ports) == 158, 'All mandatory candidates and native certificates')
        prior_rows = unpack('previousMetadata', plan['previousMetadataRawBytes'], plan['previousMetadataRawSha256'])['candidates']
        prior = {int(row['derived']['identity']): row for row in prior_rows}
        require(len(prior) == len(prior_rows) == 7480, 'All prior converted prohibitory source identities')
        selected = {int(row['derived']['identity']): row for row in metadata}
        found, seen_prior = set(), set()
        last = seen = 0
        digest = hashlib.sha256()
        with (REPO / plan['rawRelations']).open('rb') as stream:
            while line := stream.readline(2097153):
                if seen % 256 == 0:
                    check()
                require(len(line) <= 2097152 and line.endswith(b'\n') and seen < 70376, 'Complete bounded raw relation corpus')
                digest.update(line)
                element = json.loads(line)
                require(last < element['id'], 'Complete source relation ID order')
                last = element['id']
                seen += 1
                if element['id'] in selected:
                    require(element == selected[element['id']]['source'], 'Exact original mandatory source tags/members')
                    found.add(element['id'])
                if element['id'] in prior:
                    row = prior[element['id']]
                    require(element == row['source'] and derived(previous_classify(element)['rule']) == row['derived'],
                            'Every prior prohibitory source rule remains exact')
                    seen_prior.add(element['id'])
        require(seen == 70376 and found == selected.keys() and seen_prior == prior.keys() and
                digest.hexdigest() == plan['bindings'][plan['rawRelations']], 'Every original/source-derived rule and corpus seal')
        closure = unpack('closureEvidence', plan['closureRawBytes'], plan['closureRawSha256'])
        current_bytes = (REPO / plan['currentClosures']).read_bytes()
        current_ids = [v[0] for v in struct.iter_unpack('<Q', current_bytes)]
        require(len(current_ids) == 16968 and current_ids == sorted(set(current_ids)), 'Entire current native closure baseline')
        entry_bytes = (REPO / plan['currentEntryPairs']).read_bytes()
        pairs = list(struct.iter_unpack('<II', entry_bytes))
        result = overlay(closure['closingRelations'], set(prior), set(current_ids), metadata, ports, pairs, 9882872)
        require(len(result['convertedRelations']) == 30 and len(result['fallbackRelations']) == 128, 'Every qualified/fallback source outcome retains')
        flags = (REPO / plan['currentNodeFlags']).read_bytes()
        require(len(flags) == 5731903, 'Exact current source-qualified node-flag profile')
        supported_ports = [row for row in ports if row['status'] == 'source-ports-supported']
        require(all(type(row['viaAnchor']) is int and 0 <= row['viaAnchor'] < len(flags) for row in supported_ports),
                'Every certified via index binds to current flags')
        via_flag_counts = Counter(str(flags[row['viaAnchor']]) for row in supported_ports)
        # Independent per-way contributor subtraction replaces the producer's relation-union helper.
        contributors = {int(way): {int(i) for i in ids} for way, ids in closure['allClosedWayContributorIds'].items()}
        require(len(contributors) == len(result['originalClosed']) == 29657, 'Complete original contributor map')
        require({w for w, ids in contributors.items() if ids - prior.keys()} == set(current_ids), 'Current contributors independently reproduce')
        certified = set(result['convertedRelations'])
        independently_remaining = {w for w, ids in contributors.items() if ids - (prior.keys() | certified)}
        require(independently_remaining == result['closed'], 'Every independent remaining contributor exactly retained')
        independently_added = {(a, b) for row in ports if row['status'] == 'source-ports-supported'
                               for a in row['incomingPreArcIds'] for b in row['allOutgoingPreArcIds']
                               if b not in set(row['toOutgoingPreArcIds'])}
        require(independently_added == set(result['mandatoryPairs']) and
                set(result['entryPairs']) == set(pairs) | independently_added, 'All old/new native pre-arc bans independently unioned')
        changed = {int(v) for row in metadata if int(row['derived']['identity']) in certified
                   for v in [row['derived']['from_way'], row['derived']['to_way']]}
        delta = save('delta.json', {
            'previousConvertedRelationIds': [str(i) for i in sorted(prior)],
            'currentClosedWayIds': [str(i) for i in current_ids], 'oldEntryPairs': [list(pair) for pair in pairs],
            'changedWayContributorIds': {str(w): [str(i) for i in sorted(contributors[w])] for w in sorted(changed)},
            'convertedRelationIds': [str(i) for i in result['convertedRelations']],
            'fallbackRelationIds': [str(i) for i in result['fallbackRelations']],
            'openedWayIds': [str(i) for i in result['openedWayIds']],
            'mandatoryPairs': [list(pair) for pair in result['mandatoryPairs']],
            'newEntryPairs': [list(pair) for pair in result['newEntryPairs']]})
        encoded_closed = b''.join(struct.pack('<Q', i) for i in sorted(result['closed']))
        encoded_pairs = b''.join(struct.pack('<II', *pair) for pair in result['entryPairs'])
        outputs = []
        for name, raw in [('closures.bin', encoded_closed), ('entry-pairs-pre.u32', encoded_pairs)]:
            require(len(raw) < 67108864, 'Mandatory typed fact output cap')
            with (root / name).open('xb') as stream:
                stream.write(raw)
            require((root / name).read_bytes() == raw, 'Every new fact byte reopens exactly')
            outputs.append({'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        require(json.loads((root / 'delta.json').read_bytes())['openedWayIds'] == [str(i) for i in result['openedWayIds']], 'Portable delta reopens exactly')
        for name, state in before.items():
            require(state == stat_key(REPO / name), 'Every source/code input metadata unchanged: ' + name)
        save('report.json', {
            'status': 'conditional_only_contributor_and_prearc_fact_overlay_independently_audited', 'recipeSha256': args.pin,
            'allRawUnsupportedRelations': seen, 'priorConvertedSourceRulesReplayed': len(seen_prior), 'mandatoryMetadata': len(metadata),
            'convertedRules': len(certified), 'retainedFallbackRules': len(result['fallbackRelations']),
            'originalClosures': len(result['originalClosed']), 'currentClosures': len(current_ids), 'newClosures': len(result['closed']),
            'newUnclosedWayIds': len(result['openedWayIds']), 'oldPreArcPairs': len(pairs),
            'mandatoryPreArcPairsUnique': len(result['mandatoryPairs']), 'newPreArcPairs': len(result['newEntryPairs']),
            'combinedPreArcPairs': len(result['entryPairs']), 'allIndependentContributorsRetained': True,
            'allOldPreArcBansRetained': True, 'allNewBansEnterPreviouslyClosedFromWays': True,
            'oldTypedTurnsNodeFlagsPricesAndPhysicalProfileUnchanged': True,
            'certifiedViaNodeRawFlagCountsPerRule': dict(via_flag_counts),
            'certifiedRulesWhoseFromWayRemainsClosedByOtherContributors': sum(
                int(row['fromWayId']) in result['closed'] for row in supported_ports),
            'deltaArtifact': delta, 'artifacts': outputs, 'sourcePbfReads': 0, 'nativeProducerExecutions': 0,
            'routingQueries': 0, 'providerRequests': 0, 'applicationDbReads': 0, 'graphOrAppActivated': False,
            'hostMaximumRssBytes': check(), 'hostSecondsIncludingBindingsRawSourceReplayContributorAuditsAndOutput': time.monotonic() - began,
            'scope': plan['scope']})
    except BaseException as error:
        save('failure.json', {'status': 'conditional_only_overlay_stopped', 'error': repr(error)})
        raise


if __name__ == '__main__':
    main()
