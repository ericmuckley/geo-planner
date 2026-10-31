"""Read-only saved-candidate accounting; no projection or matcher replay."""
from collections import Counter
import json
import math
from pathlib import Path


def derive(root, support_path, previous_report_path):
    previous = json.loads(Path(previous_report_path).read_text())
    cached = {w['id']: w['cachedRows'] for w in previous['windows']}
    with Path(support_path).open() as stream:
        weights = {(r['windowId'], r['arc']): [s[3] for s in r['samples']] for r in map(json.loads, stream)}
    with (Path(root) / 'fragments.jsonl').open() as stream:
        records = list(map(json.loads, stream))
    assert len(weights) == len(records) == 2469
    for r in records:
        original = r['original']; key = r['windowId'], r['arc']
        assert math.isclose(math.fsum(weights[key]), original['sourceKm'], abs_tol=1e-8)
        assert all(w > 0 and math.isfinite(w) for w in weights[key])
        positive = bool(cached[r['windowId']] and not original['candidates'] and not original['searchCapped']
            and not r['searchCapped'] and any(c['hasTerminalCut'] for c in r['candidates']))
        assert r['supportsHypothesis'] is positive
        assert all(r[k] is False for k in ['sourceComplete', 'physicalIdentityVerified', 'carAccessVerified', 'usableSpeedCoverageAdmitted'])
    groups = {'all': records,
        'with_cache': [r for r in records if cached[r['windowId']]],
        'candidate_bearing': [r for r in records if r['candidates']],
        'new_clipped_positive': [r for r in records if r['supportsHypothesis']],
        'old_candidate_bearing': [r for r in records if r['original']['candidates']],
        'empty_cache': [r for r in records if not cached[r['windowId']]]}
    def summarize(group):
        union_km = []
        for r in group:
            mask = 0
            for c in r['candidates']:
                assert c['allMembersParserUsable'] == all(s == 'usable' for s in c['memberParserStatuses'])
                if c['allMembersParserUsable']: mask |= int(c['coveredSampleMaskHex'], 16)
            source_weights = weights[r['windowId'], r['arc']]
            assert mask >> len(source_weights) == 0
            union_km.append(math.fsum(w for i, w in enumerate(source_weights) if mask >> i & 1))
        return {'arcRecords': len(group), 'sourceKm': math.fsum(r['original']['sourceKm'] for r in group),
            'samples': sum(r['sampleCount'] for r in group), 'candidateVariants': sum(len(r['candidates']) for r in group),
            'originalStatusCounts': dict(Counter(r['original']['status'] for r in group)),
            'recordsWithAnyAllParserUsableCandidate': sum(any(c['allMembersParserUsable'] for c in r['candidates']) for r in group),
            'allParserUsableCandidateVariants': sum(c['allMembersParserUsable'] for r in group for c in r['candidates']),
            'parserUsableCandidateSampleUnionKm': math.fsum(union_km),
            'repeatedCandidateMemberParserOccurrences': dict(Counter(s for r in group for c in r['candidates'] for s in c['memberParserStatuses'])),
            'publisherOrdinalPathCountDistribution': dict(Counter(str(len({tuple(c['rowOrdinals']) for c in r['candidates']})) for r in group)),
            'sourceClassRecords': dict(Counter(str(r['original']['sourceClassKph']) for r in group))}
    return {'cohorts': {name: summarize(group) for name, group in groups.items()},
        'scope': 'Saved-candidate accounting only. Parser-usable sample union counts each original sample once per arc across usable annotated candidate variants. It is retained-cache opportunity, not eligible coverage, physical/global uniqueness, car access, a lower bound or ETA evidence. Cohorts overlap; arc/window km can repeat alignments. Publisher ordinal paths and repeated candidate members are not independent physical roads.'}


if __name__ == '__main__':
    repo = Path(__file__).resolve().parents[3]
    print(json.dumps(derive(repo / 'data/coarse-quality/overture-timing-fragments-v1',
        repo / 'data/coarse-quality/overture-timing-compatibility-v1/support.jsonl',
        repo / 'docs/evidence/coarse-chain-role-scope-2026-10-26/report.json'), indent=2))
