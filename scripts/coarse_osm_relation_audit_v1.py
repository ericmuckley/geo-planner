"""Stream relation-policy parity with sealed facts; never construct a road graph."""
from array import array
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_records import canonical
from coarse_timing_input import PilotError, require

KINDS = ('no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn', 'no_entry', 'no_exit',
         'only_left_turn', 'only_right_turn', 'only_straight_on', 'only_u_turn')
TURN = struct.Struct('<QQQQB7s')


def fact_rows(root, roster, prefix, shape, check=lambda: None):
    """Honor original chunk boundaries, even if a record straddles two files."""
    names = sorted(n for n in roster if n.startswith('cost-facts/'+prefix+'-'))
    require(names and len(names) <= 64, 'Relation audit fact parts')
    pending = b''
    for ordinal, name in enumerate(names):
        require(name == f'cost-facts/{prefix}-{ordinal:04d}.bin', 'Relation audit contiguous fact parts')
        path = Path(root)/name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == roster[name]['bytes'] <= 16777216, 'Relation audit fact size/type')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while raw := stream.read(65536):
                check()
                digest.update(raw)
                pending += raw
                end = len(pending)//shape.size*shape.size
                yield from shape.iter_unpack(pending[:end])
                pending = pending[end:]
        require(digest.hexdigest() == roster[name]['sha256'], 'Relation audit fact SHA')
    require(not pending, 'Relation audit partial final fact')


class RelationAudit:
    def __init__(self, expected_turns, expected_closures, expected_invalid, output, *,
                 expected_supported=409178, expected_unsupported=70376, max_output=67108864):
        self.expected_turns = iter(expected_turns)
        self.expected_closures = expected_closures
        self.expected_invalid = {r['id']: r for r in expected_invalid}
        self.expected_supported, self.expected_unsupported = expected_supported, expected_unsupported
        self.max_output, self.output = max_output, output
        require(0 <= len(expected_closures) <= 200000 and len(self.expected_invalid) <= 16, 'Relation audit input bounds')
        require(all(a < b for a, b in zip(expected_closures, expected_closures[1:])), 'Relation audit ordered expected closures')
        self.counts, self.closed, self.invalid = Counter(), set(), []
        self.bytes = 0
        self.metadata_sha = hashlib.sha256()

    def consume(self, element):
        try:
            rule = restriction_policy(element)
        except PilotError as error:
            if str(error) != 'Car prototype cannot locate unsupported restriction':
                raise
            require(element == self.expected_invalid.get(element['id']), 'Relation audit unlocatable source mismatch')
            require(len(self.invalid) < 16, 'Relation audit invalid-source cap')
            self.invalid.append(element)
            self.counts['unlocatable'] += 1
            return
        self.counts[rule['status']] += 1
        if rule['status'] == 'via-node':
            expected = next(self.expected_turns, None)
            actual = (element['id'], rule['fromWay'], rule['via'], rule['toWay'], KINDS.index(rule['kind']), b'\0'*7)
            require(actual == expected, 'Relation audit supported source turn mismatch')
        elif rule['status'] == 'closed-unsupported':
            self.closed.update(rule['memberWays'])
            require(len(self.closed) <= 200000, 'Relation audit closure-ID cap')
            raw = canonical(element)+b'\n'
            self.bytes += len(raw)
            require(len(raw) <= 2*1048576 and self.bytes <= self.max_output, 'Relation audit selected output cap')
            self.output.write(raw)
            self.metadata_sha.update(raw)

    def finish(self):
        require(next(self.expected_turns, None) is None, 'Relation audit missing supported source turn')
        require(self.counts['via-node'] == self.expected_supported, 'Relation audit supported count')
        require(self.counts['closed-unsupported'] == self.expected_unsupported, 'Relation audit unsupported count')
        require({r['id'] for r in self.invalid} == set(self.expected_invalid), 'Relation audit missing unlocatable source record')
        require(array('Q', sorted(self.closed)) == self.expected_closures, 'Relation audit full closure union mismatch')
        return {'supportedSourceTurnsMatched': self.expected_supported,
                'unsupportedRelationsRetained': self.expected_unsupported,
                'unlocatableSourceRecordsMatched': len(self.invalid), 'closureWayIdsMatched': len(self.closed),
                'classifications': dict(self.counts), 'selectedMetadataBytes': self.bytes,
                'selectedMetadataSha256': self.metadata_sha.hexdigest()}


def read_closed_ids(root, roster, check=lambda: None):
    result = array('Q')
    for identity, in fact_rows(root, roster, 'closures', struct.Struct('<Q'), check):
        require(len(result) < 200000, 'Relation audit expected closure bound')
        result.append(identity)
    return result
