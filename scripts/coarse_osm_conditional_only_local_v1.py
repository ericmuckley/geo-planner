"""Select source-corpus contributors without importing a national delta into capture."""
from analyze_osm_source_gap_closures_v2 import contribution
from coarse_timing_input import require


def local_candidates(elements, single, multi, metadata, descriptors):
    source = {row['id']: row for row in elements}
    require(len(source) == len(elements), 'Unique complete local source relation IDs')
    closing = []
    for element in elements:
        ways, _kind, _branch = contribution(element, single, multi)
        if ways:
            closing.append({'sourceRelation': element['id'], 'closedWays': [str(i) for i in sorted(ways)]})
    closing_ids = {row['sourceRelation'] for row in closing}
    require(len(metadata) == len(descriptors) <= 100000, 'Every mandatory source descriptor retained')
    local_meta, local_ports, outside = [], [], []
    previous = 0
    for row, port in zip(metadata, descriptors):
        identity = int(row['derived']['identity'])
        require(previous < identity and row['source']['id'] == identity and port['sourceRelationId'] == str(identity),
                'Exact ordered source/mandatory/certificate identity')
        previous = identity
        if identity in source:
            require(source[identity] == row['source'], 'Every local original tag/member byte agrees')
        if identity in closing_ids:
            local_meta.append(row)
            local_ports.append(port)
        else:
            outside.append({'sourceRelationId': str(identity), 'portStatus': port['status'],
                            'presentInRawSource': identity in source})
    return {'closingRelations': closing, 'metadata': local_meta, 'ports': local_ports, 'outside': outside}
