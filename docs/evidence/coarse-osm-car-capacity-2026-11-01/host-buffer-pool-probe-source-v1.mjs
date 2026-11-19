import {spawnSync} from 'node:child_process';
const operations={
 pooledBuffer:'const retain = Buffer.from("x".repeat(128));',
 progress:'await new Promise((r,j)=>process.stdout.write("x".repeat(128)+"\\n",e=>e?j(e):r()));',
 fileText:'await writeFile(file, "x".repeat(728942), {flag:"wx"});',
 fileBuffer:'await writeFile(file, Buffer.alloc(728942), {flag:"wx"});',
 hashText:'const retain = createHash("sha256").update("x".repeat(728942)).digest("hex");',
 hashBuffer:'const retain = createHash("sha256").update(new Uint8Array(1024)).digest("hex");',
 manyWitnesses:'for(let i=0;i<10000;i++)hash.update(JSON.stringify({cell:i,fromCell:i-1,from:[0.0025,0.0025],to:[0.00625,0.00125],fromSeconds:20,connectorSeconds:64}));const retain=hash.digest("hex");'
};
for(const[name,operation]of Object.entries(operations)){
 const source=`import assert from 'node:assert/strict';import{writeFile,mkdtemp,rm}from'node:fs/promises';import{createHash}from'node:crypto';
 const dir=await mkdtemp('/tmp/geo-pool-probe-');const file=dir+'/output.txt';const stream=process.stdout;const hash=createHash('sha256');
 const settle=async()=>{for(let i=0;i<4;i++){await new Promise(r=>setImmediate(r));global.gc();}};await settle();
 const keeper=Buffer.allocUnsafe(1),pool=keeper.buffer;let used=(keeper.byteOffset+8)&~7;while(used<pool.byteLength){const b=Buffer.allocUnsafe(Math.min(4088,pool.byteLength-used));assert.equal(b.buffer,pool);used=b.byteOffset+b.length;}await settle();
 const before=process.memoryUsage().arrayBuffers;${operation};await settle();const after=process.memoryUsage().arrayBuffers;assert.equal(keeper.buffer,pool);stream.write(JSON.stringify({name:${JSON.stringify(name)},before,after,extra:after-before})+'\\n');await rm(dir,{recursive:true});`;
 const r=spawnSync(process.execPath,['--expose-gc','--input-type=module','-e',source],{encoding:'utf8'});if(r.status!==0)throw new Error(r.stderr);process.stdout.write(r.stdout.trim().split('\n').at(-1)+'\n');
}
