import hashlib,json,resource,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
root=Path.cwd();folder=root/'data/experiment-pilot/two-hour-region-v1'
build=json.loads((root/'data/compact-pilot/two-hour-region-v2/build-report.json').read_text())
examples=build['importStages']['memberRoadLookups'][0]['duplicateExamples']
wanted={row['way'] for row in examples};needed=set();ways=[];records=[]
source=root/'data/coverage-pilot/two-hour-region-v2/car-roads.osm'
started=time.perf_counter()
with source.open('rb') as stream:
 parser=ET.iterparse(stream,events=('start','end'));_,document=next(parser)
 for event,element in parser:
  if event!='end' or element.tag not in {'node','way','relation'}:continue
  if element.tag=='way' and int(element.get('id')) in wanted:
   refs=[int(n.get('ref')) for n in element.findall('nd')];needed.update(refs);ways.append(ET.tostring(element))
   records.append({'way':int(element.get('id')),'nodes':refs,'tags':{t.get('k'):t.get('v') for t in element.findall('tag')}})
  document.remove(element)
with (folder/'source-duplicate-way.osm').open('xb') as output:
 output.write(b'<osm version="0.6">\n')
 with source.open('rb') as stream:
  parser=ET.iterparse(stream,events=('start','end'));_,document=next(parser)
  for event,element in parser:
   if event!='end' or element.tag not in {'node','way','relation'}:continue
   if element.tag=='node' and int(element.get('id')) in needed:output.write(ET.tostring(element))
   document.remove(element)
 for way in ways:output.write(way)
 output.write(b'</osm>\n')
result={'graphIdentity':build['graphIdentity'],'examples':examples,'sourceWays':records,'sourceArtifact':json.loads((root/'data/coverage-pilot/two-hour-region-v2/report.json').read_text())['artifacts']['car-roads.osm'],'excerptSha256':hashlib.sha256((folder/'source-duplicate-way.osm').read_bytes()).hexdigest(),'workerWallMs':(time.perf_counter()-started)*1000,'workerPeakRssBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'publicApiCalls':0,'scope':'Two read-only source XML scans on macOS under network denial; no Linux cgroup cap. Original repeated-way references and tags retained; duplicate examples are from the actual first candidate lookup, before fallback.'}
(folder/'source-repeat.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
