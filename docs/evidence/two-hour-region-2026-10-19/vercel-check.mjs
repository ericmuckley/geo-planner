import assert from 'node:assert/strict';
import { readdir, stat } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
process.env.VERCEL='1';
process.env.LOCAL_ROUTING_EXPERIMENT='1';
const directory=resolve('.vercel/output/functions/__server.func');
let bytes=0,files=0;
async function walk(path){for(const entry of await readdir(path,{withFileTypes:true})){const child=join(path,entry.name);assert.ok(!entry.name.startsWith('.env')&&!/\.(pbf|osm|csr|gph|pmtiles|py)$/.test(entry.name));if(entry.isDirectory())await walk(child);else{files++;bytes+=(await stat(child)).size;}}}
await walk(directory);
const handler=(await import(pathToFileURL(join(directory,'index.mjs')).href)).default;
let outbound=0;
globalThis.fetch=async()=>{outbound++;throw new Error('Unexpected outbound call');};
const responses=[];
for(const method of ['GET','POST']){const response=await handler.fetch(new Request('http://localhost/api/experiment',{method,...(method==='POST'?{headers:{'Content-Type':'application/json'},body:JSON.stringify({origin:{lat:32.7157,lon:-117.1611},budgetMinutes:120})}:{})}));assert.equal(response.status,503);responses.push({method,status:response.status,body:await response.json()});}
assert.equal(outbound,0);
console.log(JSON.stringify({VERCEL:'1',LOCAL_ROUTING_EXPERIMENT:'1',responses,outboundCalls:outbound,functionFiles:files,functionBytes:bytes,dataAndEnvironmentFilesBundled:false,scope:'Latest generated Vercel handler invoked locally. No cloud deployment or hosted routing request.'},null,2));
