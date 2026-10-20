import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path.cwd()/'routing'))
from anchors import file_hash,load_json
from scoped_load import load_graph
from experiment import SnapIndex
from regional_support import snap_attachments
root=Path.cwd(); directory=root/'data/compact-pilot/two-hour-region-v2'
manifest=load_json(directory/'build-manifest.json')
started=time.perf_counter();graph,model=load_graph(directory/'graph.json')
if graph.identity!=manifest['graphIdentity'] or file_hash(directory/'graph.json')!=manifest['artifacts']['graph.json']['sha256']: raise ValueError('Graph identity differs')
index=SnapIndex(graph.base.roads);rows=[]
for name,point in [('riverside',[-117.3755,33.9806]),('palm-springs',[-116.5453,33.8303]),('ensenada',[-116.6,31.8667]),('yuma',[-114.6244,32.6927])]:
    requested=list(point)
    try: expected_starts,expected_seeds,expected=snap_attachments(graph,point,100)
    except ValueError:
        _,_,nearest=snap_attachments(graph,point,5000)
        point=nearest['snapped']
        expected_starts,expected_seeds,expected=snap_attachments(graph,point,100)
    starts,seeds,snap=index.snap(graph,point,100)
    if starts!=expected_starts or seeds!=expected_seeds or snap['snapped']!=expected['snapped'] or snap['distanceMeters']!=expected['distanceMeters']: raise ValueError('Indexed/reference snap differs')
    row={'id':name,'requestedTownCenter':requested,'queryPoint':point,'snap':snap,'qualifiedPhysicalSegment':expected['physicalSegment'],'starts':[[road,str(fraction)] for road,fraction in starts],'seeds':seeds,'independentSnapIdentical':True}
    rows.append(row); print(json.dumps(row),flush=True)
result={'graphIdentity':graph.identity,'sourceGraphArtifact':manifest['artifacts']['graph.json'],'origins':rows,'workerWallMs':(time.perf_counter()-started)*1000,'publicApiCalls':0,'network':'denied by native-network.sb','scope':'Four new-area indexed snaps match the independent full-scan reference exactly. This does not independently qualify a new travel-cost field or real-world access.'}
(root/'data/experiment-pilot/two-hour-region-v1/expanded-snaps.json').write_text(json.dumps(result,indent=2)+'\n')
