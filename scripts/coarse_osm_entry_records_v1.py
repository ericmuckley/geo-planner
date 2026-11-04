"""Small typed inputs for native entry resolution; raw source records stay sealed."""
from array import array
import hashlib
import struct

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_records import strict_json
from coarse_osm_restriction_entry_v1 import entry_restriction
from coarse_timing_input import require

ENTRY = struct.Struct('<QQQQ')


def prepare(stream, candidates, fallback_output, *, expected_rows, expected_bytes,
            expected_sha256, expected_closures, check=lambda: None):
    require(0 < expected_rows <= 100000 and 0 < expected_bytes <= 67108864, 'Entry metadata input bounds')
    require(len(expected_closures) <= 200000 and all(a < b for a, b in zip(expected_closures, expected_closures[1:])), 'Entry metadata expected closure order/bound')
    digest = hashlib.sha256()
    count = size = previous = candidate_count = fallback_relations = 0
    original, fallback = set(), set()
    while raw := stream.readline(2*1048576+1):
        check()
        count += 1
        size += len(raw)
        require(len(raw) <= 2*1048576 and raw.endswith(b'\n') and count <= expected_rows and size <= expected_bytes, 'Entry metadata row/count/byte cap')
        digest.update(raw)
        element = strict_json(raw)
        identity = element.get('id')
        require(type(identity) is int and previous < identity < 2**63 and element.get('type') == 'relation', 'Entry metadata source identity/order')
        previous = identity
        old = restriction_policy(element)
        require(old['status'] == 'closed-unsupported', 'Entry metadata source classification drift')
        original.update(old['memberWays'])
        require(len(original) <= 200000, 'Entry metadata original closure bound')
        entry = entry_restriction(element)
        if entry is None:
            fallback_relations += 1
            fallback.update(old['memberWays'])
        else:
            candidates.write(ENTRY.pack(entry.identity, entry.from_way, entry.via_way, entry.to_way))
            candidate_count += 1
    require(count == expected_rows and size == expected_bytes and digest.hexdigest() == expected_sha256, 'Entry metadata complete source SHA/count/bytes')
    require(array('Q', sorted(original)) == expected_closures, 'Entry metadata full original closure union')
    for identity in sorted(fallback):
        fallback_output.write(struct.pack('<Q', identity))
    return {'sourceRows': count, 'sourceBytes': size, 'sourceSha256': digest.hexdigest(),
            'candidateRules': candidate_count, 'candidateBytes': candidate_count*ENTRY.size,
            'fallbackRelations': fallback_relations, 'fallbackClosureIds': len(fallback),
            'fallbackBytes': len(fallback)*8, 'originalClosureIdsVerified': len(original),
            'ruleShapePolicyChanged': False, 'actualArcResolutionPerformed': False}
