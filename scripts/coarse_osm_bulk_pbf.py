"""Bounded PBF framing and an optional, late-imported native iterator."""
import hashlib
from pathlib import Path
import struct
import zlib

from coarse_osm_records import canonical, utc
from coarse_timing_input import require


def fields(raw):
    def integer(offset):
        result = 0
        for shift in range(0, 70, 7):
            require(offset < len(raw), 'Truncated protobuf varint')
            byte = raw[offset]; offset += 1
            require(shift < 63 or byte <= 1, 'Protobuf integer overflow')
            result |= (byte & 127) << shift
            if byte < 128:
                require(shift == 0 or byte != 0, 'Noncanonical protobuf varint')
                return result, offset
        raise ValueError('Invalid protobuf varint')
    offset = 0
    while offset < len(raw):
        key, offset = integer(offset); number, wire = key >> 3, key & 7
        require(number > 0, 'Invalid protobuf field')
        if wire == 0: value, offset = integer(offset)
        elif wire == 2:
            length, offset = integer(offset)
            require(length <= len(raw) - offset, 'Truncated protobuf bytes')
            value = raw[offset:offset + length]; offset += length
        elif wire in (1, 5):
            length = 8 if wire == 1 else 4
            require(offset + length <= len(raw), 'Truncated fixed protobuf field')
            value = raw[offset:offset + length]; offset += length
        else: raise ValueError('Unsupported protobuf wire type')
        yield number, wire, value


def singular(raw):
    result = {}
    for key, wire, value in fields(raw):
        require(key not in result, 'Duplicate singular protobuf field')
        result[key] = wire, value
    return result


def stat_key(path):
    s = Path(path).stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def framing(path, caps, expected_state, check=lambda: None):
    """Checks frames, not entity decoding. Hash/framing IO is separately reported."""
    before = stat_key(path); count = total = 0; header = None
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with Path(path).open('rb') as stream:
        def read(size):
            nonlocal total
            check(); raw = stream.read(size); sha.update(raw); md5.update(raw); total += len(raw)
            require(len(raw) == size, 'Truncated PBF frame'); return raw
        while True:
            check(); prefix = stream.read(4)
            if not prefix: break
            sha.update(prefix); md5.update(prefix); total += len(prefix)
            require(len(prefix) == 4, 'Truncated PBF frame length')
            size = struct.unpack('!I', prefix)[0]
            require(0 < size < caps['pbfHeaderBytesExclusiveMaximum'], 'PBF header bound')
            bh = singular(read(size))
            require(bh.get(1, (None,))[0] == 2 and bh.get(3, (None,))[0] == 0, 'PBF frame header fields')
            kind, length = bh[1][1], bh[3][1]
            limit = caps['pbfUncompressedBlobBytesExclusiveMaximum']
            require(0 < length <= limit + 65536, 'Compressed PBF blob bound')
            blob = singular(read(length))
            require(set(blob) <= {1, 2, 3} and ((1 in blob) != (3 in blob)), 'Unsupported PBF compression/blob fields')
            if 1 in blob:
                require(blob[1][0] == 2, 'Invalid raw PBF blob')
                payload = blob[1][1]
            else:
                require(blob.get(2, (None,))[0] == 0 and blob[3][0] == 2 and 0 < blob[2][1] < limit, 'PBF raw size bound')
                decoder = zlib.decompressobj(); payload = decoder.decompress(blob[3][1], blob[2][1] + 1)
                require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(payload) == blob[2][1], 'Invalid/oversized PBF decompression')
            require(len(payload) < limit, 'Decoded PBF blob bound')
            if 2 in blob: require(blob[2] == (0, len(payload)), 'PBF raw-size disagreement')
            if kind == b'OSMHeader':
                require(header is None and count == 0, 'Duplicate/late PBF source header')
                features, timestamp = [], None
                for key, wire, value in fields(payload):
                    if key == 4:
                        require(wire == 2, 'PBF feature wire'); features.append(value.decode('utf-8'))
                    if key == 32:
                        require(wire == 0 and timestamp is None, 'PBF timestamp field'); timestamp = value
                import datetime
                require(timestamp is not None and features and len(features) == len(set(features)), 'Missing PBF identity/features')
                require('OsmSchema-V0.6' in features and set(features) <= {'OsmSchema-V0.6', 'DenseNodes'}, 'Unsupported PBF required features/history')
                state = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                require(state == expected_state, 'PBF publisher state drift')
                header = {'publisherStateUtc': state, 'requiredFeatures': sorted(features)}
            else:
                require(kind == b'OSMData' and header is not None, 'Unexpected PBF block/order')
                settings = {}
                for key, wire, value in fields(payload):
                    if key in (17, 18, 19, 20):
                        require(wire == 0 and key not in settings, 'Invalid/duplicate primitive scale')
                        settings[key] = value if value < 2**63 else value - 2**64
                require(0 < settings.get(17, 100) < 2**31 and settings.get(17, 100) % 100 == 0, 'Unsupported sub-OSM coordinate precision')
                require(0 < settings.get(18, 1000) < 2**31 and settings.get(18, 1000) % 1000 == 0, 'Unsupported subsecond source precision')
                require(all(settings.get(k, 0) % 100 == 0 for k in (19, 20)), 'Unsupported coordinate offset precision')
            count += 1; check()
    require(header is not None and total == before[2] and stat_key(path) == before, 'PBF source changed/missing header')
    return {**header, 'framingBytesRead': total, 'frames': count, 'sourceSha256': sha.hexdigest(), 'sourceMd5': md5.hexdigest()}


def native_records(path, max_record_bytes):
    """Actual library ABI/round-trip qualification remains a later tool-stage gate."""
    import osmium
    processor = osmium.FileProcessor(str(path))  # Deliberately no with_locations().
    for obj in processor:
        stamp = obj.timestamp
        require(stamp.microsecond == 0 and stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0, 'Unsupported native timestamp precision/zone')
        raw = {'type': {'n': 'node', 'w': 'way', 'r': 'relation'}[obj.type_str()], 'id': int(obj.id),
            'version': int(obj.version), 'timestamp': obj.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'), 'visible': bool(obj.visible)}
        # Copy while the decoder's view is valid; bound variable-size copies incrementally.
        charged = 256; tags = {}
        for tag in obj.tags:
            charged += len(tag.k.encode()) + len(tag.v.encode()) + 64
            require(charged <= max_record_bytes, 'Native view tag-copy bound'); require(str(tag.k) not in tags, 'Duplicate native tag key'); tags[str(tag.k)] = str(tag.v)
        raw['tags'] = tags
        if raw['type'] == 'node': raw.update(lon=float(obj.location.lon), lat=float(obj.location.lat))
        elif raw['type'] == 'way':
            refs = []
            for node in obj.nodes:
                charged += 32; require(charged <= max_record_bytes, 'Native view reference-copy bound'); refs.append(int(node.ref))
            raw['nodes'] = refs
        else:
            members = []
            for member in obj.members:
                charged += len(member.role.encode()) + 128
                require(charged <= max_record_bytes, 'Native view member-copy bound')
                members.append({'type': {'n': 'node', 'w': 'way', 'r': 'relation'}[member.type], 'ref': int(member.ref), 'role': str(member.role)})
            raw['members'] = members
        require(len(canonical(raw)) <= max_record_bytes, 'Native copied-record bound')
        utc(raw['timestamp']); yield raw
