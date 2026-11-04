"""One frozen host containment diagnostic; source/model admission stays false."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_polygon_review_v1 import parse_poly,review_window
from coarse_timing_input import require

OUTPUT='data/coarse-quality/us-osm-polygon-review-v1'


def main(recipe,pin):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve();body=recipe.read_bytes()
    require(recipe.is_relative_to(repo/'docs/evidence') and hashlib.sha256(body).hexdigest()==pin,'Polygon review recipe binding')
    plan=json.loads(body);require(plan['output']==OUTPUT and plan['windows']==21 and plan['wallSeconds']==30 and plan['modelChanged'] is False,'Polygon review scope')
    root=repo/OUTPUT;require(not root.exists(),'Polygon review fresh output');root.mkdir();(root/'execution-plan.json').write_bytes(body);began=time.monotonic()
    try:
        for name,expected in plan['inputs'].items():
            path=repo/name;require(path.is_file() and not path.is_symlink() and path.stat().st_size<=131072,'Polygon review input type/size')
            require(hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Polygon review input drift')
        windows=json.loads((repo/plan['proposal']).read_bytes())['windows'];require(len(windows)==21,'Polygon review fixed windows')
        results={}
        for label,path in plan['polygons'].items():
            rings=parse_poly((repo/path).read_bytes());views=[]
            for window in windows:
                require(time.monotonic()-began<30,'Polygon review deadline');views.append(review_window(window,rings))
            results[label]={'sha256':plan['inputs'][path],'rings':len(rings),'holes':sum(r['hole'] for r in rings),
                            'vertices':sum(len(r['points']) for r in rings),'windows':views,
                            'strictlyContainedWindows':sum(v['strictlyInsideReviewedPolygon'] for v in views)}
        result={'status':'host_polygon_diagnostic_complete','polygons':results,'seconds':time.monotonic()-began,
                'sourceSnapshotBoundaryQualified':False,'roadCompletenessQualified':False,'all21WindowsAdequate':False,'modelChanged':False,
                'scope':'Exact rational planar corner/boundary containment in these two saved polygons. Not OGC topology validation, proof of the effective dated extraction boundary, or proof about omitted road segments.'}
        code=0
    except Exception as error:result={'status':'stopped','errorType':type(error).__name__,'error':str(error)[:2000],'sourceOrModelAdmitted':False};code=2
    encoded=(json.dumps(result,indent=2)+'\n').encode();require(len(encoded)<=1048576,'Polygon review output cap');(root/'result.json').write_bytes(encoded);return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');args=parser.parse_args();raise SystemExit(main(args.recipe,args.sha256))
