"""Read saved lane-rejected source tags; no new eligibility or routing policy."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import sqlite3
import sys
import time

from coarse_osm_backbone_v1 import MAJOR
from coarse_osm_car_conditional_speed_v1 import way_policy


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(path):
    stat=path.stat()
    return stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns


def run(recipe,pin):
    began=time.monotonic();repo=Path(__file__).resolve().parents[1]
    assert sha(recipe)==pin
    plan=json.loads(recipe.read_bytes())
    assert plan['output']=='data/coarse-quality/us-osm-lane-metadata-capture-v1'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+8388608<72*1024**3
    for name,expected in plan['bindings'].items():assert sha(repo/name)==expected
    database=repo/plan['database'];before=identity(database)
    assert database.is_file() and not database.is_symlink() and database.stat().st_size==plan['databaseBytes']==336826368
    assert sha(database)==plan['databaseSha256']
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def check():
        assert time.monotonic()-began<120
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<4*1024**3
    try:
        db=sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
        counts=Counter();forms=Counter();rows=[];seen=previous=0
        try:
            assert db.execute("SELECT count(*) FROM objects WHERE kind='way'").fetchone()[0]==239253
            query="SELECT id,json_extract(CAST(raw AS TEXT),'$.tags') FROM objects WHERE kind='way' AND json_extract(CAST(raw AS TEXT),'$.tags.highway') IN ("+','.join('?' for _ in MAJOR)+") ORDER BY id"
            for way,encoded in db.execute(query,MAJOR):
                assert previous<way and isinstance(encoded,str) and len(encoded.encode())<=4194304
                previous=way;seen+=1;assert seen<=28995
                tags=json.loads(encoded);assert isinstance(tags,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in tags.items())
                policy=way_policy(tags);counts[str(policy.reason)]+=1
                if policy.reason=='lane-access':
                    lane_tags={key:value for key,value in tags.items() if 'lanes' in key}
                    forms.update((key,value) for key,value in lane_tags.items())
                    rows.append({'id':way,'tags':tags,'laneTags':lane_tags,'currentPolicy':asdict(policy)})
                    assert len(rows)<=1000 and len(forms)<=5000
                if seen%1024==0:check()
        finally:db.close()
        assert seen==28995 and len(rows)==32
        assert identity(database)==before and sha(database)==plan['databaseSha256'] and identity(database)==before
        report={'status':'captured_lane_rejection_metadata_inventory_complete','recipeSha256':pin,
                'capturedWayRows':239253,'majorWayRowsClassified':seen,'currentReasonCounts':dict(counts),
                'laneRejectedWays':len(rows),'laneKeyValueCounts':[{'key':key,'value':value,'ways':count} for (key,value),count in forms.most_common()],
                'rows':rows,'immutableSourcePreserved':True,'sourcePbfReads':0,'nativeConstructorExecutions':0,'routingQueries':0,'providerRequests':0,'applicationDbOperations':0,'policyChanged':False,
                'hostSecondsIncludingBindingsSqliteReadAndSourceHashes':time.monotonic()-began,
                'scope':'Saved captured source SQLite read-only/immutable,not the application DB. All28995major ways classified by the existing policy;32lane-rejected raw tag sets retained without interpretation or eligibility changes. Captured metadata is not national lane feasibility/causal detour/permission/ETA proof. No coordinates,new source acquisition,PBF,graph/query/provider/app operation.'}
        raw=(json.dumps(report,indent=2)+'\n').encode();assert len(raw)<=1048576
        (root/'report.json').write_bytes(raw);check()
        print(json.dumps({k:report[k] for k in ['status','majorWayRowsClassified','laneRejectedWays','laneKeyValueCounts','hostSecondsIncludingBindingsSqliteReadAndSourceHashes']}))
    except BaseException as error:
        (root/'failure.json').write_text(json.dumps({'error':repr(error),'hostSeconds':time.monotonic()-began})+'\n');raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin')
    args=parser.parse_args();run(args.recipe,args.pin)
