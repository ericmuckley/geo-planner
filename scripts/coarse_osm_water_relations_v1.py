"""Versioned water projection of the qualified fixed relation-tail reader.

The whole source identity and completed native semantic census are prerequisites.
Earlier node/way bodies are not decoded again by this selected metadata stage.
"""
from pathlib import Path
import hashlib
import struct
import time

from coarse_osm_bulk_pbf import fields, singular
from coarse_osm_relation_tail_v1 import MIB, payload, header_state, relation_tags
from coarse_timing_input import require
from diagnose_osm_member_v2 import decode_relation


def source_guard(path, expected, check=lambda: None):
    from coarse_osm_bulk_pbf import stat_key
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Water relation source file/type')
    before = stat_key(path)
    size = 0
    digest, md5 = hashlib.sha256(), hashlib.md5()
    began = time.monotonic()
    with path.open('rb') as stream:
        while raw := stream.read(8*MIB):
            check()
            size += len(raw)
            require(size <= expected['bytes'], 'Water relation source size cap')
            digest.update(raw)
            md5.update(raw)
    require(size == expected['bytes'] and digest.hexdigest() == expected['sha256'] and
            md5.hexdigest() == expected['md5'] and stat_key(path) == before, 'Water relation source identity/stat')
    return {'bytes':size,'sha256':digest.hexdigest(),'md5':md5.hexdigest(),'stat':before,'seconds':time.monotonic()-began}


def water_relations(path, *, source_bytes, state, expected_relations, consume,
                       tail_bytes=256*MIB, compressed_cap=320*MIB,
                       decoded_cap=4*1024**3, frame_cap=500000, check=lambda: None):
    """Stream all water-tag relations; preserve every member, role and raw tag."""
    require(0 < source_bytes and 0 < expected_relations <= 2000000, 'Relation tail source/count bound')
    require(0 < tail_bytes <= 256*MIB and compressed_cap <= 320*MIB and decoded_cap <= 4*1024**3, 'Relation tail work caps')
    cutoff = max(0, source_bytes-tail_bytes)
    frames = compressed = decoded = relations = selected = previous = 0
    header_seen = False
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size == source_bytes, 'Relation tail source size/type')
    with path.open('rb') as stream:
        while prefix := stream.read(4):
            check()
            frames += 1
            require(len(prefix) == 4 and frames <= frame_cap, 'Relation tail frame count/prefix')
            length = struct.unpack('!I', prefix)[0]
            require(0 < length < 65536, 'Relation tail BlobHeader size')
            raw_header = stream.read(length)
            require(len(raw_header) == length, 'Relation tail truncated BlobHeader')
            h = singular(raw_header)
            require(set(h) <= {1, 2, 3} and h.get(1, (None,))[0] == 2 and h.get(3, (None,))[0] == 0, 'Relation tail BlobHeader fields')
            kind, size = h[1][1], h[3][1]
            require(kind in (b'OSMHeader', b'OSMData') and 0 < size <= 32*MIB+65536 and stream.tell()+size <= source_bytes, 'Relation tail frame bounds')
            if kind == b'OSMHeader':
                require(frames == 1 and not header_seen, 'Relation tail duplicate/late header')
                header_state(payload(stream.read(size)), state)
                header_seen = True
                continue
            require(header_seen, 'Relation tail missing source header')
            if stream.tell()+size < cutoff:
                stream.seek(size, 1)
                continue
            compressed += size
            require(compressed <= compressed_cap, 'Relation tail compressed cap')
            data = payload(stream.read(size))
            decoded += len(data)
            require(decoded <= decoded_cap, 'Relation tail decoded cap')
            primitive = list(fields(data))
            tables = [v for k, w, v in primitive if k == 1 and w == 2]
            dates = [v for k, w, v in primitive if k == 18 and w == 0]
            require(len(tables) == 1 and len(dates) <= 1, 'Relation tail primitive settings')
            strings = []
            for k, w, value in fields(tables[0]):
                require(k == 1 and w == 2, 'Relation tail string table')
                strings.append(value)
            granularity = dates[0] if dates else 1000
            require(strings and 0 < granularity < 2**31 and granularity % 1000 == 0, 'Relation tail date granularity')
            for key, wire, group in primitive:
                if key != 2:
                    continue
                require(wire == 2, 'Relation tail group wire')
                for tag, wire, raw in fields(group):
                    if tag != 4:
                        continue
                    require(wire == 2, 'Relation tail relation wire')
                    identity, tags = relation_tags(raw, strings)
                    require(identity > previous, 'Relation tail duplicate/out-of-order identity')
                    previous = identity
                    relations += 1
                    require(relations <= expected_relations, 'Relation tail count overflow')
                    if not (tags.get('natural') == 'water' or tags.get('waterway') == 'riverbank' or tags.get('landuse') == 'reservoir'):
                        continue
                    element, stats = decode_relation(raw, strings, granularity)
                    require(element['id'] == identity and element['tags'] == tags and 0 < element['version'] <= 2**31-1 and element['visible'] and '1970-01-01T00:00:00Z' <= element['timestamp'] <= state, 'Relation tail selected metadata')
                    require(stats['invalidMemberIdentitiesOrTypes'] == 0 and stats['canonicalBytes'] <= 2*MIB, 'Relation tail selected member/record bound')
                    consume(element)
                    selected += 1
            check()
        require(stream.tell() == source_bytes and header_seen and relations == expected_relations, 'Relation tail complete relation count/EOF')
    return {'relations': relations, 'waterRecordsSelected': selected,
            'headersVisited': frames, 'compressedTailBytes': compressed, 'decodedTailBytes': decoded,
            'earlierNodeWayBodiesValidated': False, 'nodeWayObjectsProjected': 0}
