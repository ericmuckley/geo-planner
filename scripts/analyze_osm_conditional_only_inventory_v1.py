"""Complete cached only-turn metadata inventory; no physical ports or graph changes."""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_conditional_node_inventory_v1 import closure_unions
from coarse_osm_conditional_node_turns_v2 import classify as previous_classify
from coarse_osm_conditional_only_node_v1 import POLICY, classify
from coarse_osm_country_screen_v1 import owned_usage
from coarse_timing_input import require

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def derived(rule):
    return {key: str(value) if type(value) is int else value for key, value in asdict(rule).items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    recipe = REPO / args.plan
    require(sha(recipe) == args.pin, 'Only-turn inventory recipe binding')
    plan = json.loads(recipe.read_bytes())
    require(plan['output'] == 'data/coarse-quality/us-osm-conditional-only-inventory-v1' and plan['policy'] == POLICY,
            'Exact only-turn inventory namespace/policy')
    require(plan['priorReserveBytes'] + plan['newClosedAllocationBytes'] + plan['metadataScratchReserveBytes'] + 67108864 < 72 * 1024**3,
            'Only-turn inventory aggregate reservation')
    for name, pin in plan['bindings'].items():
        require(not name.endswith(('.pbf', '/001.bin')) and sha(REPO / name) == pin, 'Only-turn read-only binding: ' + name)
    root = REPO / plan['output']
    root.mkdir()
    (root / 'execution-plan.json').write_bytes(recipe.read_bytes())

    def check():
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        require(time.monotonic() - began < 300 and rss < 536870912 and owned_usage(root)['conservativeAllocatedBytes'] < 67108864,
                'Only-turn host deadline/RSS/owned cap')
        return rss

    def save(name, value, limit=1048576):
        raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
        require(len(raw) <= limit, 'Only-turn output byte cap')
        with (root / name).open('xb') as stream:
            stream.write(raw)
        return {'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    try:
        with gzip.open(REPO / plan['previousMetadata'], 'rb') as stream:
            raw = stream.read(16777217)
        require(len(raw) == plan['previousMetadataRawBytes'] <= 16777216 and
                hashlib.sha256(raw).hexdigest() == plan['previousMetadataRawSha256'], 'Complete prior converted metadata')
        prior_rows = json.loads(raw)['candidates']
        prior = {int(row['derived']['identity']): row for row in prior_rows}
        require(len(prior) == len(prior_rows) == 7480, 'All current converted prohibitory relations')
        reasons, kinds = Counter(), Counter()
        candidates, seen_prior = [], set()
        source = REPO / plan['rawRelations']
        before = stat_key(source)
        seen = last = 0
        digest = hashlib.sha256()
        with source.open('rb') as stream:
            while line := stream.readline(2097153):
                if seen % 256 == 0:
                    check()
                require(len(line) <= 2097152 and line.endswith(b'\n') and seen < 70376, 'Complete bounded relation corpus')
                digest.update(line)
                element = json.loads(line)
                require(last < element['id'], 'Strict original relation ID order')
                last = element['id']
                seen += 1
                if element['id'] in prior:
                    old = prior[element['id']]
                    require(old['source'] == element and derived(previous_classify(element)['rule']) == old['derived'],
                            'Every current prohibitory source/derived identity retains')
                    seen_prior.add(element['id'])
                result = classify(element)
                reasons[result['reason']] += 1
                if result['rule'] is not None:
                    require(element['id'] not in prior, 'No mandatory/prohibitory candidate overlap')
                    row = derived(result['rule'])
                    kinds[row['kind']] += 1
                    candidates.append({'source': element, 'derived': row})
        require(seen == 70376 and digest.hexdigest() == plan['bindings'][plan['rawRelations']] and before == stat_key(source),
                'Complete ordered source count/seal/stable metadata')
        require(seen_prior == prior.keys(), 'Every prior converted relation reproduced')
        with gzip.open(REPO / plan['closureEvidence'], 'rb') as stream:
            raw = stream.read(33554433)
        require(len(raw) == plan['closureRawBytes'] <= 33554432 and hashlib.sha256(raw).hexdigest() == plan['closureRawSha256'],
                'Complete independent original closure evidence')
        closure = json.loads(raw)
        original, current = closure_unions(closure['closingRelations'], set(prior))
        closed_bytes = (REPO / plan['currentClosures']).read_bytes()
        require(len(closed_bytes) == 16968 * 8, 'Current source closure byte width')
        closed_ids = [v[0] for v in struct.iter_unpack('<Q', closed_bytes)]
        require(closed_ids == sorted(set(closed_ids)) and current == set(closed_ids), 'Exact entire current closure set')
        require(len(original) == 29657 and original == {int(k) for k in closure['allClosedWayContributorIds']},
                'Entire original closure union reproduces')
        selected = {int(row['derived']['identity']) for row in candidates}
        _, remaining = closure_unions(closure['closingRelations'], set(prior) | selected)
        require(remaining <= current, 'Every independent unconverted contributor retains')
        potential = sorted(current - remaining)
        asset = save('candidate-metadata.json', {'candidates': candidates,
                     'potentialUnclosedWayIdsBeforeSourcePortValidation': [str(i) for i in potential]}, 16777216)
        restored = json.loads((root / asset['file']).read_bytes())
        require(restored['candidates'] == candidates, 'Every original tag/member/derived row roundtrips')
        for index, row in enumerate(restored['candidates']):
            if index % 256 == 0:
                check()
            require(derived(classify(row['source'])['rule']) == row['derived'], 'Every mandatory source replays after reopen')
        save('report.json', {
            'status': 'all_cached_conditional_only_metadata_feasibility_audited', 'recipeSha256': args.pin, 'policy': POLICY,
            'allRawUnsupportedRelations': seen, 'classificationCounts': dict(reasons), 'metadataCandidates': len(candidates),
            'candidateKinds': dict(kinds), 'allCurrentProhibitoryRelationsSourceReplayed': len(seen_prior),
            'allOriginalWayClosuresIndependentlyReconstructed': len(original), 'allCurrentWayClosuresExact': len(current),
            'potentialUnclosedWaysBeforeSourcePortValidation': len(potential),
            'potentialRemainingClosedWaysBeforeSourcePortValidation': len(remaining),
            'everyIndependentUnconvertedContributorRetained': True, 'physicalSourcePortsValidated': False,
            'artifact': asset, 'hostSecondsIncludingBindingsClassificationsClosureUnionsAndReplay': time.monotonic() - began,
            'hostMaximumRssBytes': check(), 'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'routingQueries': 0,
            'providerRequests': 0, 'applicationDbReads': 0, 'sourcePermissionsOrPricesChanged': False, 'appActivated': False,
            'scope': plan['scope']})
    except BaseException as error:
        save('failure.json', {'status': 'conditional_only_inventory_stopped', 'error': repr(error)})
        raise


if __name__ == '__main__':
    main()
