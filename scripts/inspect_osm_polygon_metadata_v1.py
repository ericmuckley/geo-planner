"""One bounded public-metadata snapshot; no PBF, routing provider or native calls."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import ssl
import time
import urllib.error
import urllib.request

from coarse_timing_input import require

ROOT='data/coarse-quality/us-osm-polygon-metadata-v1'
API='https://api.github.com/repos/geofabrik/polygons_download.geofabrik.de/commits'
RAW='https://raw.githubusercontent.com/geofabrik/polygons_download.geofabrik.de/'
POLYGON='https://download.geofabrik.de/north-america/us.poly'
CAPS={'requests':4,'bodyBytesEach':131072,'totalBodyBytes':524288,'ownedBytes':2097152,'wallSeconds':120}


def main(recipe,pin):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve();body=recipe.read_bytes()
    require(recipe.is_relative_to(repo/'docs/evidence') and hashlib.sha256(body).hexdigest()==pin,'Polygon metadata recipe binding')
    plan=json.loads(body);require(plan['output']==ROOT and plan['caps']==CAPS and plan['sourceSnapshotUtc']=='2026-10-25T21:21:21Z' and plan['sourceSha256']=='1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff','Polygon metadata exact scope')
    require(plan['producerSha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'Polygon metadata producer binding')
    root=repo/ROOT;require(not root.exists(),'Polygon metadata fresh output required');root.mkdir();(root/'execution-plan.json').write_bytes(body)
    began=time.monotonic();records=[];total=0
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=131072,'Polygon metadata record cap')
        path=root/name;require(not path.exists(),'Polygon metadata refuses overwrite');path.write_bytes(raw)
        require(sum(p.stat().st_size for p in root.iterdir())<=CAPS['ownedBytes'],'Polygon metadata storage cap')
    def check():require(time.monotonic()-began<CAPS['wallSeconds'],'Polygon metadata deadline')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    def fetch(url):
        nonlocal total
        check();require(len(records)<CAPS['requests'],'Polygon metadata request cap')
        index=len(records)+1;request=urllib.request.Request(url,headers={'User-Agent':'geo-planner-source-review/1','Accept':'application/json' if url.startswith(API) else 'text/plain','Accept-Encoding':'identity'})
        receipt={'url':url,'attempt':index,'status':'attempted'};records.append(receipt);chunks=[]
        try:
            try:response=opener.open(request,timeout=min(25,CAPS['wallSeconds']-(time.monotonic()-began)))
            except urllib.error.HTTPError as error:response=error
            with response:
                receipt.update(httpStatus=response.code,finalUrl=response.geturl(),headers={k.lower():v[:2048] for k,v in response.headers.items() if k.lower() in ('content-type','content-length','last-modified','etag','date')})
                size=0
                while size<=CAPS['bodyBytesEach']:
                    check();chunk=response.read(min(16384,CAPS['bodyBytesEach']+1-size))
                    if not chunk:break
                    chunks.append(chunk);size+=len(chunk)
            raw=b''.join(chunks);total+=len(raw);path=root/f'{index:03d}.bin';path.write_bytes(raw)
            receipt.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),path=path.name,truncatedAtCap=len(raw)>CAPS['bodyBytesEach'])
            require(len(raw)<=CAPS['bodyBytesEach'] and total<=CAPS['totalBodyBytes'],'Polygon metadata response/body cap')
            require(response.code==200 and response.geturl()==url,'Polygon metadata status/redirect')
            receipt['status']='received';return raw
        finally:save(f'{index:03d}-receipt.json',receipt)
    try:
        historical=json.loads(fetch(plan['historicalCommitsUrl']));require(isinstance(historical,list) and len(historical)==1,'Polygon metadata historical commit count')
        commit=historical[0];identity=commit['sha'];date=commit['commit']['committer']['date']
        require(re.fullmatch('[0-9a-f]{40}',identity) is not None and datetime.fromisoformat(date)<=datetime.fromisoformat(plan['sourceSnapshotUtc']),'Polygon metadata commit identity/date')
        old=fetch(RAW+identity+'/polygons/us.poly');current=fetch(POLYGON);changes=json.loads(fetch(plan['laterCommitsUrl']))
        require(isinstance(changes,list) and len(changes)<=1,'Polygon metadata change-list bound')
        save('result.json',{'status':'metadata_snapshot_complete','historicalCommit':identity,'historicalCommitUtc':date,
             'repositoryPolygonSha256':hashlib.sha256(old).hexdigest(),'currentDeployedPolygonSha256':hashlib.sha256(current).hexdigest(),
             'repositoryAndCurrentDeployedBytesEqual':old==current,'noRepositoryChangesInCheckedInterval':not changes,
             'sourceSnapshotBoundaryCryptographicallyBound':False,'allWindowsAdequate':False,'modelChanged':False,
             'scope':'Repository history and current deployed bytes only. Deployment state on the source date, effective parent clipping, window geometry and long-crossing completeness need separate review.'})
        code=0
    except Exception as error:
        save('failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:2000],'sourceOrModelAdmitted':False});code=2
    save('run-summary.json',{'exitCode':code,'requestsAttempted':len(records),'bodyBytes':total,'seconds':time.monotonic()-began,'pbfOrRoutingRequests':0,'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');args=parser.parse_args();raise SystemExit(main(args.recipe,args.sha256))
