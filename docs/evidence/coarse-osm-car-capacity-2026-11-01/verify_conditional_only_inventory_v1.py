"""Saved metadata proof; optional small cached-source reconciliation, never graph/PBF reads."""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
import struct
import sys

from verify_boundary_coverage_pilot_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha

sys.path[:0] = [str(REPO / 'scripts'), str(REPO / 'routing')]
from coarse_osm_conditional_only_node_v1 import POLICY, classify


def verify(local_assets=False):
    result = previous()
    plan = load(HERE / 'conditional-only-inventory-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO / name) == pin, name
    report = stage('conditional-only-inventory-v1')
    closed = load(HERE / 'conditional-only-inventory-v1-closed-v1.json')
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 415
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < 67108864
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    assert report['status'] == 'all_cached_conditional_only_metadata_feasibility_audited'
    assert report['recipeSha256'] == sha(HERE / 'conditional-only-inventory-plan-v1.json')
    assert report['policy'] == plan['policy'] == POLICY
    assert report['allRawUnsupportedRelations'] == sum(report['classificationCounts'].values()) == 70376
    mirror = HERE / 'conditional-only-inventory-v1-raw-v1'
    metadata = load(mirror / report['artifact']['file'])
    asset = closed['roster'][report['artifact']['file']]
    assert not asset['ignoredLargeAsset']
    assert all(asset[k] == report['artifact'][k] for k in ['bytes', 'sha256'])
    rows = metadata['candidates']
    ids = [int(row['derived']['identity']) for row in rows]
    assert ids == sorted(set(ids))
    assert len(rows) == report['metadataCandidates'] == sum(report['candidateKinds'].values()) == 158
    assert dict(Counter(row['derived']['kind'] for row in rows)) == report['candidateKinds']
    for row in rows:
        rule = classify(row['source'])['rule']
        assert rule is not None
        assert {k: str(v) if type(v) is int else v for k, v in asdict(rule).items()} == row['derived']
    potential = [int(v) for v in metadata['potentialUnclosedWayIdsBeforeSourcePortValidation']]
    assert potential == sorted(set(potential)) and len(potential) == report['potentialUnclosedWaysBeforeSourcePortValidation'] == 288
    assert report['allCurrentProhibitoryRelationsSourceReplayed'] == 7480
    assert report['allOriginalWayClosuresIndependentlyReconstructed'] == 29657
    assert report['allCurrentWayClosuresExact'] == 16968
    assert report['potentialRemainingClosedWaysBeforeSourcePortValidation'] == 16968 - len(potential)
    assert report['everyIndependentUnconvertedContributorRetained'] and not report['physicalSourcePortsValidated']
    assert report['sourcePbfReads'] == report['sourceConstructorExecutions'] == report['routingQueries'] == report['providerRequests'] == report['applicationDbReads'] == 0
    assert not report['sourcePermissionsOrPricesChanged'] and not report['appActivated']
    assert report['hostMaximumRssBytes'] < 536870912
    assert report['hostSecondsIncludingBindingsClassificationsClosureUnionsAndReplay'] < 300
    if local_assets:
        for name, pin in plan['bindings'].items():
            if name.startswith('data/'):
                assert sha(REPO / name) == pin, name
        counts = Counter()
        originals = []
        digest = hashlib.sha256()
        last = seen = 0
        with (REPO / plan['rawRelations']).open('rb') as stream:
            for line in stream:
                digest.update(line)
                element = json.loads(line)
                assert element['id'] > last
                last = element['id']
                seen += 1
                classified = classify(element)
                counts[classified['reason']] += 1
                if classified['rule'] is not None:
                    originals.append(element)
        assert seen == 70376 and dict(counts) == report['classificationCounts']
        assert digest.hexdigest() == plan['bindings'][plan['rawRelations']]
        assert originals == [row['source'] for row in rows]
        with gzip.open(REPO / plan['previousMetadata'], 'rt') as stream:
            prior = {int(r['derived']['identity']) for r in json.load(stream)['candidates']}
        with gzip.open(REPO / plan['closureEvidence'], 'rt') as stream:
            closure = json.load(stream)
        current = {value[0] for value in struct.iter_unpack('<Q', (REPO / plan['currentClosures']).read_bytes())}
        contributors = {int(way): {int(i) for i in values} for way, values in closure['allClosedWayContributorIds'].items()}
        # Independent per-way contributor calculation, not the producer's relation-union helper.
        assert {way for way, source_ids in contributors.items() if source_ids - prior} == current
        proposed = {way for way, source_ids in contributors.items() if source_ids - (prior | set(ids))}
        assert current - proposed == set(potential) and proposed <= current
        assert len(contributors) == 29657 and len(proposed) == 16680
    return {**result, 'status': 'conditional_only_metadata_source_rows_and_contributor_bounds_reconciled',
            'registeredClosedRoots': 416, 'newUniqueClosedAllocationBytes': total,
            'conditionalOnlyMetadataCandidates': len(rows), 'conditionalOnlyPotentialUnclosedWays': len(potential),
            'conditionalOnlyPhysicalSourcePortsValidated': False,
            'conditionalOnlyCachedCorpusAndPerWayContributorsReconciled': local_assets,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-assets', action='store_true')
    print(json.dumps(verify(parser.parse_args().local_assets)))
