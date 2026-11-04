"""Bounded selected relation projection from a parent-qualified fixed PBF tail.

This does not validate or project earlier node/way bodies. The caller binds the
whole immutable source and parent seals, then requires complete relation parity.
"""
import datetime
from pathlib import Path
import struct
import zlib

from coarse_osm_bulk_pbf import fields, singular
from coarse_timing_input import require
from diagnose_osm_member_v2 import decode_relation, unpack

MIB = 1048576


def payload(blob):
    data = singular(blob)
    require(set(data) <= {1, 2, 3} and ((1 in data) != (3 in data)), 'Relation tail blob fields')
    if 1 in data:
        require(data[1][0] == 2, 'Relation tail raw wire')
        raw = data[1][1]
    else:
        require(data.get(2, (None,))[0] == 0 and 0 < data[2][1] < 32*MIB and data[3][0] == 2, 'Relation tail compressed shape')
        decoder = zlib.decompressobj()
        raw = decoder.decompress(data[3][1], data[2][1]+1)
        require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(raw) == data[2][1], 'Relation tail decompression')
    require(len(raw) < 32*MIB and (2 not in data or data[2] == (0, len(raw))), 'Relation tail raw bound')
    return raw


def header_state(raw, expected):
    features, stamp = [], None
    for key, wire, value in fields(raw):
        if key == 4:
            require(wire == 2, 'Relation tail header feature wire')
            features.append(value.decode('utf8'))
        if key == 32:
            require(wire == 0 and stamp is None, 'Relation tail header timestamp')
            stamp = value
    require('OsmSchema-V0.6' in features and len(features) == len(set(features)) and set(features) <= {'OsmSchema-V0.6', 'DenseNodes'}, 'Relation tail required features')
    require(stamp is not None and datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') == expected, 'Relation tail publisher state')


def relation_tags(raw, strings):
    """Inspect IDs/tags first; ordinary non-restriction members stay packed."""
    identity, keys, values = None, [], []
    for key, wire, value in fields(raw):
        if key == 1:
            require(wire == 0 and identity is None and 0 < value < 2**63, 'Relation tail identity')
            identity = value
        if key in (2, 3):
            require(wire in (0, 2), 'Relation tail tag wire')
            (keys if key == 2 else values).extend([value] if wire == 0 else unpack(value))
    require(identity is not None and len(keys) == len(values) <= 262144, 'Relation tail tags')
    tags = {}
    for k, v in zip(keys, values):
        require(0 <= k < len(strings) and 0 <= v < len(strings), 'Relation tail string-table index')
        key, value = strings[k].decode('utf8'), strings[v].decode('utf8')
        require(key not in tags, 'Relation tail duplicate tags')
        tags[key] = value
    return identity, tags


def selected_relations(path, *, source_bytes, state, expected_relations, consume,
                       tail_bytes=256*MIB, compressed_cap=320*MIB,
                       decoded_cap=4*1024**3, frame_cap=500000, check=lambda: None):
    """Stream restriction records, retaining no country node/way dictionaries."""
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
                    if not tags.get('type', '').startswith('restriction'):
                        continue
                    element, stats = decode_relation(raw, strings, granularity)
                    require(element['id'] == identity and element['tags'] == tags and 0 < element['version'] <= 2**31-1 and element['visible'] and '1970-01-01T00:00:00Z' <= element['timestamp'] <= state, 'Relation tail selected metadata')
                    require(stats['invalidMemberIdentitiesOrTypes'] == 0 and stats['canonicalBytes'] <= 2*MIB, 'Relation tail selected member/record bound')
                    consume(element)
                    selected += 1
            check()
        require(stream.tell() == source_bytes and header_seen and relations == expected_relations, 'Relation tail complete relation count/EOF')
    return {'relations': relations, 'restrictionRecordsSelected': selected,
            'headersVisited': frames, 'compressedTailBytes': compressed, 'decodedTailBytes': decoded,
            'earlierNodeWayBodiesValidated': False, 'nodeWayObjectsProjected': 0}
