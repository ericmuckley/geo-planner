"""All graph blockers versus cached raw nodes and every restriction contributor."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from coarse_osm_blocked_node_causes_v1 import node_cause
from coarse_osm_car_policy_v1 import restriction_policy

REPO = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stat(path):
    value = path.stat()
    return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    args = parser.parse_args()
    began = time.monotonic()
    plan_path = REPO/args.plan
    assert sha(plan_path) == args.pin
    plan = json.loads(plan_path.read_bytes())
    for name,pin in plan['bindings'].items():
        assert sha(REPO/name) == pin,name
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes'] < 72*1024**3
    cache_source = json.loads((REPO/plan['cacheSourcePlan']).read_bytes())['source']
    current_source = json.loads((REPO/plan['currentSourcePlan']).read_bytes())['source']
    assert cache_source['sha256'] == current_source['sha256'] and cache_source['bytes'] == current_source['bytes']

    def check():
        assert time.monotonic()-began < 600, 'Blocked-node cause analysis deadline'

    mapped = json.loads((REPO/plan['mappingReport']).read_bytes())
    artifact = mapped['artifacts']['blocked-nodes.json.gz']
    path = REPO/plan['mappingRoot']/'blocked-nodes.json.gz'
    assert path.stat().st_size == artifact['bytes'] and sha(path) == artifact['sha256']
    raw = gzip.decompress(path.read_bytes())
    assert len(raw) == artifact['rawBytes'] and hashlib.sha256(raw).hexdigest() == artifact['rawSha256']
    nodes = json.loads(raw)
    assert len(nodes) == 13776
    by_id = {int(row['sourceNodeId']):row for row in nodes}
    by_vertex = {row['vertex']:int(row['sourceNodeId']) for row in nodes}
    assert len(by_id) == len(by_vertex) == 13776
    contributors = defaultdict(list)
    relation_details = {}
    all_relation_nodes = set()
    metadata = REPO/plan['relationMetadata']
    metadata_before = stat(metadata)
    count = previous = size = 0
    digest = hashlib.sha256()
    with metadata.open('rb') as stream:
        while line := stream.readline(2097153):
            check();count += 1;size += len(line);digest.update(line)
            assert len(line) <= 2097152 and line.endswith(b'\n') and count <= 70376
            element = json.loads(line)
            assert previous < element['id'];previous = element['id']
            classified = restriction_policy(element)
            assert classified['status'] == 'closed-unsupported'
            all_relation_nodes.update(classified['memberNodes'])
            matched = set(classified['memberNodes']).intersection(by_id)
            for identity in matched:
                contributors[identity].append(element['id'])
            if matched:
                relation_details[str(element['id'])] = {'tags':element['tags'],'members':element['members'],
                                                       'matchedGraphNodeIds':[str(value) for value in sorted(matched)]}
    assert count == 70376 and len(all_relation_nodes) == 1833
    assert size == plan['relationBytes'] and digest.hexdigest() == plan['relationSha256']
    assert stat(metadata) == metadata_before
    database = (REPO/plan['cacheDatabase']).resolve()
    before = stat(database)
    assert before[2] == plan['cacheBytes'] and sha(database) == plan['cacheSha256']
    db = sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True)
    db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
    evidence = {}
    raw_known = set()
    source_sqlite_queries = 0
    try:
        for identity,row in sorted(by_id.items()):
            if source_sqlite_queries % 256 == 0:
                check()
            raw_node = None
            if identity < 2**63:
                source_sqlite_queries += 1
                found = db.execute("SELECT id,raw FROM objects WHERE kind='node' AND id=?",(identity,)).fetchone()
                if found is not None:
                    assert found[0] == identity and len(found[1]) <= 1048576
                    original = json.loads(found[1])
                    assert original.get('type','node') == 'node' and original.get('id',identity) == identity
                    if isinstance(original.get('tags'),dict):
                        raw_node = {'type':'node','id':identity,'tags':original['tags']}
                        raw_known.add(identity)
            evidence[identity] = node_cause(identity,row['flags'],raw_node,contributors.get(identity,[]))
    finally:
        db.close()
    assert stat(database) == before and sha(database) == plan['cacheSha256'] and stat(database) == before
    trials = json.loads((REPO/plan['trialReport']).read_bytes())
    assert len(trials['rows']) == 83 and trials['originalCases'] == 83
    cases = []
    trial_ids = set()
    for row in trials['rows']:
        check()
        artifact = row['asset']
        assert Path(artifact['filename']).name == artifact['filename']
        path = REPO/plan['trialRoot']/artifact['filename']
        assert path.stat().st_size == artifact['compressedBytes'] <= 2097152 and sha(path) == artifact['sha256']
        with gzip.open(path,'rb') as stream:
            raw = stream.read(33554433)
        assert len(raw) == artifact['rawBytes'] <= 33554432 and hashlib.sha256(raw).hexdigest() == artifact['rawSha256']
        saved = json.loads(raw)
        assert saved['id'] == row['id']
        selected = [by_vertex[vertex] for vertex in saved['crossedBlockedVertices']]
        assert len(selected) == row['blockedVerticesCrossed']
        trial_ids.update(selected)
        cases.append({'id':row['id'],'optimisticRoadLegSavingsTicks':row['savingsTicks'],
                      'crossedBlockedNativeNodeIds':[str(value) for value in selected],
                      'rawNodesKnown':sum(value in raw_known for value in selected),
                      'withRestrictionContributors':sum(bool(contributors.get(value)) for value in selected)})
    assert len({row['id'] for row in cases}) == 83
    keep = raw_known | set(contributors) | trial_ids
    mismatch = [str(identity) for identity in sorted(raw_known)
                if evidence[identity]['sourceBlockingReconciled'] is False or evidence[identity]['sourceSignalReconciled'] is False]
    report = {'status':'all_blocked_graph_nodes_cached_raw_tags_and_restriction_contributors_audited',
              'recipeSha256':args.pin,'blockedGraphNodes':13776,'rawNodesKnown':len(raw_known),
              'unknownRawNodeIds':[str(value) for value in sorted(set(by_id)-raw_known)],
              'nodeEvidence':{str(value):evidence[value] for value in sorted(keep)},
              'sourceReconciliationMismatchNodeIds':mismatch,
              'allRawUnsupportedRelationsRead':count,'allUnsupportedRelationNodeIds':len(all_relation_nodes),
              'blockedGraphNodesWithRestrictionContributors':len(contributors),'relationDetails':relation_details,
              'knownRawCauseCounts':dict(Counter(evidence[value]['cause'] for value in sorted(raw_known))),
              'all83TrialAttachmentsRetained':cases,'uniqueTrialBlockedNativeNodes':len(trial_ids),
              'trialBlockedNodesRawKnown':sum(value in raw_known for value in trial_ids),
              'trialBlockedNodesWithRestrictionContributors':sum(bool(contributors.get(value)) for value in trial_ids),
              'sameSourcePbfSha256':current_source['sha256'],'cachedSourceSqliteQueries':source_sqlite_queries,
              'sourcePbfReads':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
              'sourcePermissionsOrPricesChanged':False,'appActivated':False,
              'hostSecondsIncludingBindingsAllNodeQueriesContributorsAndTrialJoins':time.monotonic()-began,
              'scope':'ALL13776blocked graph native IDs, ALL70376cached raw unsupported relations and ALL83optimistic fixed-attachment trial records. Cached raw-node archive and current source recipes share the same source PBF hash; every missing raw node remains UNKNOWN, never inferred benign. Raw base-node policy and independent restriction-member-node contributions remain separate. Matching stored flags does not grant passage; every remaining contributor/base block must be honored before any generic correction. Optimistic savings are not lawful routes/point predictions/new accuracy/model admission. Readonly immutable local source SQLite only, no application DB/network/PBF/model queries or price/permission changes.'}
    encoded = (json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
    assert len(encoded) <= 16777216
    with (REPO/plan['output']).open('xb') as stream:
        stream.write(encoded)
    print(json.dumps({key:report[key] for key in ['status','blockedGraphNodes','rawNodesKnown','knownRawCauseCounts','uniqueTrialBlockedNativeNodes','trialBlockedNodesRawKnown','trialBlockedNodesWithRestrictionContributors','sourceReconciliationMismatchNodeIds','hostSecondsIncludingBindingsAllNodeQueriesContributorsAndTrialJoins']}))


if __name__ == '__main__':
    main()
