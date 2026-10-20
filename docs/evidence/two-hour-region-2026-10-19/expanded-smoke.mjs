import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const source=await readFile('data/experiment-pilot/two-hour-region-v1/expanded-snaps.json');
const proof=JSON.parse(source);
const output='data/experiment-pilot/two-hour-areas-v2';
await mkdir(output);
const samples=[];
for(const origin of proof.origins){let previous=0;for(const minutes of [60,120]){
  const query={origin:{lat:origin.queryPoint[1],lon:origin.queryPoint[0]},budgetMinutes:minutes};
  const started=performance.now();
  const response=await fetch('http://127.0.0.1:3000/api/experiment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(query),signal:AbortSignal.timeout(90000)});
  const raw=await response.text();const httpMs=performance.now()-started;
  await writeFile(`${output}/${origin.id}-${minutes}.json`,raw,{flag:'wx'});
  assert.equal(response.status,200,raw.slice(0,300));
  const result=JSON.parse(raw),m=result.metadata;
  assert.deepEqual(result.query,query);assert.equal(m.graphIdentity,proof.graphIdentity);
  assert.deepEqual(m.snap.snapped,origin.snap.snapped);assert.equal(m.snap.distanceMeters,origin.snap.distanceMeters);
  assert.ok(m.display.reachableDirectedRoads>0&&m.display.reachableDirectedRoads>=previous);previous=m.display.reachableDirectedRoads;
  assert.equal(m.publicApiCalls,0);assert.equal(m.coverageVerified,false);assert.equal(m.truncated,m.reachedCutNodes>0);
  assert.ok(m.display.displayedSegments<=30000);
  if(m.truncated)assert.ok(m.warnings.some(w=>w.startsWith('INCOMPLETE:')));
  samples.push({origin:origin.id,minutes,httpMs,responseBytes:Buffer.byteLength(raw),metadata:m});
  console.log(`${origin.id} ${minutes}m: ${m.display.reachableDirectedRoads} roads, ${m.reachedCutNodes} edges, ${httpMs.toFixed(1)} ms HTTP`);
}}
await writeFile(`${output}/report.json`,JSON.stringify({graphIdentity:proof.graphIdentity,independentSnapProofSha256:createHash('sha256').update(source).digest('hex'),samples,publicApiCalls:0,coverageVerified:false,scope:'Eight live app smoke queries in the expanded region, including the Arizona border area. Snaps match independent full scans; new-origin full cost fields and real-world access are not independently qualified.'},null,2)+'\n',{flag:'wx'});
