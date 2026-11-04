"""Lossless water relation records and independently audited member-way closure."""
from array import array
import gzip
import hashlib
import json
from pathlib import Path
import sys

from coarse_timing_input import require

MAX_MEMBERS = 500000
MAX_RAW = 256*1048576
MAX_GZIP = 32*1048576
MAX_LINE = 8*1048576


def counters():
    return dict.fromkeys(('relations','wayMembers','nodeMembers','relationMembers',
                          'outerWayMembers','innerWayMembers','otherRoleWayMembers',
                          'multipolygons','otherTypes','maxMembers'), 0)


def add(counts, element, ways):
    members = element['members']
    counts['relations'] += 1
    counts['maxMembers'] = max(counts['maxMembers'], len(members))
    counts['multipolygons' if element['tags'].get('type') == 'multipolygon' else 'otherTypes'] += 1
    for member in members:
        kind = member['type']
        require(kind in ('way','node','relation') and 0 < member['ref'] < 2**63, 'Water member identity/type')
        counts[kind+'Members'] += 1
        if kind == 'way':
            counts[member['role']+'WayMembers' if member['role'] in ('outer','inner') else 'otherRoleWayMembers'] += 1
            ways.append(member['ref'])
        require(counts['wayMembers']+counts['nodeMembers']+counts['relationMembers'] <= MAX_MEMBERS, 'Water relation member cap')


class RelationStore:
    def __init__(self, root):
        self.root = Path(root)
        self.raw = (self.root/'water-relations.jsonl.gz').open('xb')
        self.stream = gzip.GzipFile(filename='',mode='wb',fileobj=self.raw,mtime=0)
        self.counts = counters()
        self.ways = array('Q')
        self.previous = self.bytes = 0
        self.digest = hashlib.sha256()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        try:
            self.stream.close()
        finally:
            self.raw.close()

    def consume(self, element):
        require(element['id'] > self.previous, 'Water relation output order')
        self.previous = element['id']
        add(self.counts, element, self.ways)
        raw = (json.dumps(element,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
        self.bytes += len(raw)
        require(len(raw) <= MAX_LINE and self.bytes <= MAX_RAW, 'Water relation raw output cap')
        self.digest.update(raw)
        self.stream.write(raw)
        require(self.raw.tell() <= MAX_GZIP, 'Water relation gzip cap')

    def finish(self):
        self.close()
        require((self.root/'water-relations.jsonl.gz').stat().st_size <= MAX_GZIP, 'Water relation final gzip cap')
        ids = array('Q')
        for identity in sorted(self.ways):
            if not ids or ids[-1] != identity:
                ids.append(identity)
        require(sys.byteorder == 'little' and ids.itemsize == 8, 'Water member index platform')
        with (self.root/'member-way-ids.u64').open('xb') as stream:
            ids.tofile(stream)
        return {'counts':self.counts,'uniqueMemberWays':len(ids),'rawJsonBytes':self.bytes,
                'rawJsonSha256':self.digest.hexdigest(),'gzipBytes':(self.root/'water-relations.jsonl.gz').stat().st_size,
                'memberIndexBytes':len(ids)*8}


def audit(root, expected, check=lambda: None):
    """Reconstruct roles/counts/ID index from saved JSON without the writer helpers."""
    root = Path(root)
    counts = counters()
    way_ids = set()
    previous = raw_bytes = 0
    digest = hashlib.sha256()
    with gzip.open(root/'water-relations.jsonl.gz','rb') as stream:
        while raw := stream.readline(MAX_LINE+1):
            check()
            raw_bytes += len(raw)
            require(raw.endswith(b'\n') and len(raw) <= MAX_LINE and raw_bytes <= MAX_RAW, 'Water audit line/byte cap')
            digest.update(raw)
            row = json.loads(raw)
            tags = row['tags']
            require(row['type'] == 'relation' and row['id'] > previous and
                    (tags.get('natural') == 'water' or tags.get('waterway') == 'riverbank' or tags.get('landuse') == 'reservoir'), 'Water audit selected order/type/tags')
            previous = row['id']
            counts['relations'] += 1
            counts['maxMembers'] = max(counts['maxMembers'],len(row['members']))
            counts['multipolygons' if tags.get('type') == 'multipolygon' else 'otherTypes'] += 1
            for member in row['members']:
                kind, role, identity = member['type'],member['role'],member['ref']
                require(kind in ('node','way','relation') and isinstance(role,str) and 0 < identity < 2**63, 'Water audit member fields')
                if kind == 'node': counts['nodeMembers'] += 1
                elif kind == 'relation': counts['relationMembers'] += 1
                else:
                    counts['wayMembers'] += 1
                    if role == 'outer': counts['outerWayMembers'] += 1
                    elif role == 'inner': counts['innerWayMembers'] += 1
                    else: counts['otherRoleWayMembers'] += 1
                    way_ids.add(identity)
    require(counts == expected['counts'] and raw_bytes == expected['rawJsonBytes'] and digest.hexdigest() == expected['rawJsonSha256'], 'Water audit exact metadata/counters')
    with (root/'member-way-ids.u64').open('rb') as stream:
        for identity in sorted(way_ids):
            require(stream.read(8) == identity.to_bytes(8,'little'), 'Water audit exact member-way index')
        require(not stream.read(1), 'Water audit member-way index EOF')
    require(len(way_ids) == expected['uniqueMemberWays'] and len(way_ids)*8 == expected['memberIndexBytes'], 'Water audit index dimensions')
    return {'allSelectedRelationsChecked':counts['relations'],'allMemberOccurrencesChecked':sum(counts[k] for k in ('wayMembers','nodeMembers','relationMembers')),
            'uniqueMemberWayIdsChecked':len(way_ids),'rawJsonBytesChecked':raw_bytes,
            'nestedAndOtherRoleMembersPreserved':True,'geometryOrMissingReferencesResolved':False}
