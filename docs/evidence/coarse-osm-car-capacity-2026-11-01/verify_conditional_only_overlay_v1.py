"""Reconstruct closure/ban delta bytes from portable certificates, without graph execution."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import struct

from verify_conditional_only_ports_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify(local_assets=False):
    result = previous()
    prefix = 'conditional-only-overlay-v1'
    report = stage(prefix)
    closed = load(HERE / (prefix + '-closed-v1.json'))
    plan = load(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert report['status'] == 'conditional_only_contributor_and_prearc_fact_overlay_independently_audited'
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 419
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < 67108864
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    assert report['recipeSha256'] == sha(HERE / 'conditional-only-overlay-plan-v1.json')
    asset = report['deltaArtifact']
    assert all(closed['roster'][asset['file']][k] == asset[k] for k in ['bytes', 'sha256'])
    assert not closed['roster'][asset['file']]['ignoredLargeAsset']
    delta = load(HERE / (prefix + '-raw-v1') / asset['file'])

    def identities(name):
        values = [int(i) for i in delta[name]]
        assert values == sorted(set(values)) and all(0 < i < 2**63 for i in values)
        return set(values)

    prior = identities('previousConvertedRelationIds')
    current = identities('currentClosedWayIds')
    converted = identities('convertedRelationIds')
    fallback = identities('fallbackRelationIds')
    opened = identities('openedWayIds')
    assert len(prior) == 7480 and len(current) == 16968 and len(converted) == 30 and len(fallback) == 128
    assert not prior & converted and not converted & fallback
    original_closed = b''.join(struct.pack('<Q', i) for i in sorted(current))
    assert hashlib.sha256(original_closed).hexdigest() == plan['bindings'][plan['currentClosures']]
    old_pairs = [tuple(pair) for pair in delta['oldEntryPairs']]
    assert old_pairs == sorted(set(old_pairs)) and all(type(i) is int and 0 <= i < 9882872 for pair in old_pairs for i in pair)
    encoded_old = b''.join(struct.pack('<II', *pair) for pair in old_pairs)
    assert hashlib.sha256(encoded_old).hexdigest() == plan['bindings'][plan['currentEntryPairs']]
    ports = load(HERE / 'conditional-only-ports-run-raw-v1/source-port-descriptors.json')['rows']
    assert converted == {int(row['sourceRelationId']) for row in ports if row['status'] == 'source-ports-supported'}
    assert fallback == {int(row['sourceRelationId']) for row in ports if row['status'] != 'source-ports-supported'}
    supported = [row for row in ports if row['status'] == 'source-ports-supported']
    changed = {int(row[key]) for row in supported for key in ['fromWayId', 'toWayId']}
    contributors = {int(way): {int(i) for i in ids} for way, ids in delta['changedWayContributorIds'].items()}
    assert set(contributors) == changed
    for row in supported:
        identity = int(row['sourceRelationId'])
        assert int(row['fromWayId']) in current
        assert all(identity in contributors[int(row[key])] for key in ['fromWayId', 'toWayId'])
    assert all(bool(ids - prior) == (way in current) for way, ids in contributors.items())
    independently_opened = {way for way, ids in contributors.items() if way in current and not ids - (prior | converted)}
    assert opened == independently_opened and len(opened) == 49
    remaining = current - opened
    additions = {(a, b) for row in supported for a in row['incomingPreArcIds']
                 for b in row['allOutgoingPreArcIds'] if b not in row['toOutgoingPreArcIds']}
    assert sorted(additions) == [tuple(pair) for pair in delta['mandatoryPairs']]
    assert sorted(additions - set(old_pairs)) == [tuple(pair) for pair in delta['newEntryPairs']]
    combined = sorted(set(old_pairs) | additions)
    outputs = {
        'closures.bin': b''.join(struct.pack('<Q', i) for i in sorted(remaining)),
        'entry-pairs-pre.u32': b''.join(struct.pack('<II', *pair) for pair in combined)}
    for item in report['artifacts']:
        raw = outputs[item['file']]
        assert item['bytes'] == len(raw) and item['sha256'] == hashlib.sha256(raw).hexdigest()
        assert all(closed['roster'][item['file']][k] == item[k] for k in ['bytes', 'sha256'])
    assert report['newClosures'] == len(remaining) == 16919
    assert report['newUnclosedWayIds'] == len(opened)
    assert report['oldPreArcPairs'] == len(old_pairs) == 25398
    assert report['combinedPreArcPairs'] == len(combined) == 25436
    assert report['mandatoryPreArcPairsUnique'] == report['newPreArcPairs'] == len(additions) == 38
    assert report['allRawUnsupportedRelations'] == 70376 and report['priorConvertedSourceRulesReplayed'] == 7480
    assert report['mandatoryMetadata'] == report['convertedRules'] + report['retainedFallbackRules'] == 158
    for key in ['allIndependentContributorsRetained', 'allOldPreArcBansRetained',
                'allNewBansEnterPreviouslyClosedFromWays', 'oldTypedTurnsNodeFlagsPricesAndPhysicalProfileUnchanged']:
        assert report[key]
    assert report['certifiedRulesWhoseFromWayRemainsClosedByOtherContributors'] == sum(int(r['fromWayId']) in remaining for r in supported) == 2
    assert sum(report['certifiedViaNodeRawFlagCountsPerRule'].values()) == 30
    assert report['hostMaximumRssBytes'] < 536870912
    assert report['hostSecondsIncludingBindingsRawSourceReplayContributorAuditsAndOutput'] < 300
    assert report['sourcePbfReads'] == report['nativeProducerExecutions'] == report['routingQueries'] == report['providerRequests'] == report['applicationDbReads'] == 0
    assert not report['graphOrAppActivated']
    if local_assets:
        for name, pin in plan['bindings'].items():
            if name.startswith('data/'):
                assert sha(REPO / name) == pin, name
        with gzip.open(REPO / plan['previousMetadata'], 'rt') as stream:
            assert {int(row['derived']['identity']) for row in json.load(stream)['candidates']} == prior
        with gzip.open(REPO / plan['closureEvidence'], 'rt') as stream:
            source = json.load(stream)
        full = {int(way): {int(i) for i in ids} for way, ids in source['allClosedWayContributorIds'].items()}
        assert contributors == {way: full[way] for way in changed}
        assert {way for way, ids in full.items() if ids - prior} == current
        assert {way for way, ids in full.items() if ids - (prior | converted)} == remaining
        flags = (REPO / plan['currentNodeFlags']).read_bytes()
        assert dict(Counter(str(flags[row['viaAnchor']]) for row in supported)) == report['certifiedViaNodeRawFlagCountsPerRule']
        for name, raw in outputs.items():
            assert (REPO / plan['output'] / name).read_bytes() == raw
    return {**result, 'status': 'mandatory_closure_and_prearc_delta_bytes_independently_reconstructed_native_pending',
            'registeredClosedRoots': 420, 'newUniqueClosedAllocationBytes': total,
            'conditionalOnlyConvertedContributors': len(converted),
            'conditionalOnlyNewlyUnclosedSourceWayIds': len(opened), 'conditionalOnlyNewClosureIds': len(remaining),
            'conditionalOnlyCombinedPreArcPairs': len(combined),
            'conditionalOnlySourceContributorAndFlagAssetsReconciled': local_assets,
            'conditionalOnlyNativeGraphQualified': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-assets', action='store_true')
    print(json.dumps(verify(parser.parse_args().local_assets)))
