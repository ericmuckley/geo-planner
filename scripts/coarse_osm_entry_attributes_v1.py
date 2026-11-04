"""Attach closed source speed/default/road-class facts to all selected path arcs.

Country columns remain typed arrays; only the bounded selected path-arc set
becomes Python objects. No node coordinates, source PBF, routes or cost fitting.
"""
from array import array
from bisect import bisect_left
import math
from pathlib import Path
import struct

from coarse_osm_car_packed_audit_v1 import ARC, rows, unpack24

ROLES = ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link')


def annotate(source, offset_path, map_path, selected, dimensions, check=lambda: None):
    way_count, vertices, pre_count, post_count = dimensions
    assert 0 < way_count <= 8000000 and 0 < vertices <= 0xffffff and 0 < post_count <= pre_count <= 0xffffff
    assert len(selected) <= 200000 and all(type(n) is int and 0 <= n < post_count for n in selected)
    source = Path(source)
    ids, forward, backward, flags = array('Q'), array('d'), array('d'), array('I')
    for identity, f, b, flag, _ in rows(source, 'ways', struct.Struct('<QddII')):
        assert len(ids) < way_count and identity > 0 and (not ids or ids[-1] < identity)
        assert all(math.isfinite(v) and 0 <= v <= 160 for v in (f, b))
        assert bool(flag & 1) == (f > 0) and bool(flag & 2) == (b > 0)
        assert (flag >> 4) & 15 < len(ROLES)
        ids.append(identity); forward.append(f); backward.append(b); flags.append(flag)
    assert len(ids) == way_count
    blocked = bytearray(way_count)
    previous = 0
    for identity, in rows(source, 'closures', struct.Struct('<Q')):
        assert previous < identity
        previous = identity
        at = bisect_left(ids, identity)
        if at < way_count and ids[at] == identity:
            blocked[at] = 1
    assert Path(offset_path).is_file() and not Path(offset_path).is_symlink() and Path(offset_path).stat().st_size == 3*(vertices+1) <= 67108864
    assert Path(map_path).is_file() and not Path(map_path).is_symlink() and Path(map_path).stat().st_size == 4*post_count <= 67108864
    offsets = unpack24(Path(offset_path).read_bytes())
    mapping = array('I')
    mapping.frombytes(Path(map_path).read_bytes())
    assert len(offsets) == vertices+1 and offsets[0] == 0 and offsets[-1] == post_count
    assert all(a <= b for a, b in zip(offsets, offsets[1:])) and len(mapping) == post_count
    seen = bytearray((post_count+7)//8)
    for arc in mapping:
        assert arc < post_count and not seen[arc >> 3] & (1 << (arc & 7))
        seen[arc >> 3] |= 1 << (arc & 7)
    del seen
    cursor = array('I', offsets[:-1])
    output = {}
    pre = retained = 0
    for tail, head, way, first, last, direction, padding, ms in rows(source, 'arcs', ARC):
        pre += 1
        assert pre <= pre_count and tail < vertices and head < vertices and way < way_count
        assert first < last and direction in (-1, 1) and padding == b'\0'*3 and 0 < ms <= 0xffffffff*125
        if pre % 65536 == 0:
            check()
        if blocked[way]:
            continue
        old_arc = cursor[tail]
        assert old_arc < offsets[tail+1]
        cursor[tail] += 1
        retained += 1
        arc = mapping[old_arc]
        if arc not in selected:
            continue
        fwd = direction == 1
        speed = forward[way] if fwd else backward[way]
        assert speed > 0
        output[arc] = {'sourceWay': ids[way], 'sourcePreArc': pre-1, 'sourceCsrArc': old_arc,
                       'role': ROLES[(flags[way] >> 4) & 15], 'direction': direction,
                       'defaultSpeed': bool(flags[way] & (4 if fwd else 8)),
                       'sourceSpeedKph': speed, 'sourceFullCostTicks': (ms+124)//125}
    assert (pre, retained) == (pre_count, post_count) and cursor == array('I', offsets[1:])
    assert set(output) == selected
    check()
    return output


def summarize(record, attributes):
    groups = {}
    steps = record['road']['steps'] if record['road'] is not None else []
    for step in steps:
        source = attributes[step['arc']]
        ticks = step['ticks']
        assert type(ticks) is int and 0 <= ticks <= source['sourceFullCostTicks']
        if step['portion'] == 'full':
            assert ticks == source['sourceFullCostTicks']
        key = source['role']+'/'+('default' if source['defaultSpeed'] else 'tagged')
        group = groups.setdefault(key, {'ticks': 0, 'steps': 0, 'speedMinKph': source['sourceSpeedKph'], 'speedMaxKph': source['sourceSpeedKph']})
        group['ticks'] += ticks
        group['steps'] += 1
        group['speedMinKph'] = min(group['speedMinKph'], source['sourceSpeedKph'])
        group['speedMaxKph'] = max(group['speedMaxKph'], source['sourceSpeedKph'])
    assert sum(group['ticks'] for group in groups.values()) == record['components']['roadTravelTicks']
    total = record['components']['roadTravelTicks']
    return {'id': record['sample']['id'], 'roadTicks': total, 'groups': groups,
            'defaultTicks': sum(g['ticks'] for key, g in groups.items() if key.endswith('/default')),
            'taggedTicks': sum(g['ticks'] for key, g in groups.items() if key.endswith('/tagged'))}
