"""Complete captured tag parity, immutable source and no coordinate projection."""
from dataclasses import asdict
import hashlib
import json
import sqlite3
from coarse_osm_car_conditional_speed_v1 import POLICY,node_policy,restriction_policy,way_policy
from inventory_osm_car_conditional_scope_v1 import selected_ordinals
from coarse_timing_input import require


def run(native,repo,check=lambda:None):
    source=repo/'data/coarse-quality/us-osm-disk-capture-run-v1/extract/audit-selected.sqlite'
    pin=json.loads((repo/'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json').read_bytes())['roster']['extract/audit-selected.sqlite']
    def stat():
        s=source.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns]
    def sha():
        with source.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    before=stat();require(before[2]==pin['bytes'] and sha()==pin['sha256'],'Sealed captured source')
    selected=selected_ordinals((repo/'data/coarse-quality/us-osm-lineage-run-v1/provenance/selected-nodes.u32').read_bytes())
    require(len(selected)==143560,'Selected native-node denominator')
    db=sqlite3.connect(source.as_uri()+'?mode=ro&immutable=1',uri=True)
    db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
    counts={'selectedNodes':0,'majorWays':0,'relations':0,'sourceWaysExamined':0,'sourceNodeIdsVisited':0}
    def compare(kind,tags,members=()):
        if kind=='way':expected=asdict(way_policy(tags))
        elif kind=='node':expected={k:v for k,v in node_policy(tags).items() if k in ('blocked','signal','tagged')}
        else:
            result=restriction_policy({'id':1,'tags':tags,'members':members})
            expected={k:result.get(k,0 if k in ('fromWay','via','toWay') else None) for k in ('status','kind','fromWay','via','toWay','reason')}
        require(native.classify(kind,tags,members)==expected,'Complete captured native parity: '+kind)
    try:
        cursor=0
        for ordinal,(_,raw) in enumerate(db.execute("SELECT id,json_extract(CAST(raw AS TEXT),'$.tags') FROM objects WHERE kind='node' ORDER BY id")):
            counts['sourceNodeIdsVisited']+=1
            if ordinal%8192==0:check()
            if cursor<len(selected) and ordinal==selected[cursor]:compare('node',json.loads(raw));cursor+=1;counts['selectedNodes']+=1
        counts['sourceWaysExamined']=db.execute("SELECT count(*) FROM objects WHERE kind='way'").fetchone()[0]
        query="SELECT id,json_extract(CAST(raw AS TEXT),'$.tags') FROM objects WHERE kind='way' AND json_extract(CAST(raw AS TEXT),'$.tags.highway') IN ("+','.join('?' for _ in POLICY['roles'])+") ORDER BY id"
        for _,raw in db.execute(query,POLICY['roles']):
            if counts['majorWays']%1024==0:check()
            compare('way',json.loads(raw));counts['majorWays']+=1
        for _,tags,members in db.execute("SELECT id,json_extract(CAST(raw AS TEXT),'$.tags'),json_extract(CAST(raw AS TEXT),'$.members') FROM objects WHERE kind='relation' ORDER BY id"):
            if counts['relations']%1024==0:check()
            compare('relation',json.loads(tags),json.loads(members));counts['relations']+=1
    finally:db.close()
    require(counts=={'selectedNodes':143560,'majorWays':28995,'relations':4900,'sourceWaysExamined':239253,'sourceNodeIdsVisited':1123919},'Complete captured denominators')
    require(stat()==before and sha()==pin['sha256'] and stat()==before,'Source unchanged after captured parity');check()
    return {'status':'passed_complete_captured_metadata_native_policy_equivalence',**counts,'sourceStatBefore':before,'sourceStatAfter':stat(),'sourceSha256':pin['sha256'],
            'nodeCoordinatesProjected':0,'sourcePbfReads':0,'networkRequests':0,'applicationDbReads':0,'nationalArtifactBuilt':False,'etaQualified':False,'vercelQualified':False,'modelChanged':False}
