import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { unpooledUtf8 } from "./coarse_osm_host_output_v1.ts";

test("host output preserves UTF-8 bytes without a shared slab", () => {
	for (const text of ["", "progress\n", "Unicode: 🙂 £\n"]) {
		const encoded = unpooledUtf8(text);
		assert.equal(encoded.toString("utf8"), text);
		assert.equal(encoded.buffer.byteLength, encoded.length);
		assert.equal(encoded.byteOffset, 0);
	}
});

test("a fresh Buffer slab adds 8KiB; disabling host pooling and unpooled output restore exactly", () => {
	for (const mode of ["pooled", "disabled", "explicit"]) {
		const script = `
import assert from 'node:assert/strict';
import { disableHostBufferPooling, writeHostProgress } from ${JSON.stringify(new URL("./coarse_osm_host_output_v1.ts", import.meta.url).href)};
const stream = process.stdout;
const settle = async () => { for(let i=0;i<4;i++){ await new Promise(r=>setImmediate(r)); global.gc(); } };
await settle();
const keeper = Buffer.allocUnsafe(1);
const pool = keeper.buffer;
let used = (keeper.byteOffset + keeper.length + 7) & ~7;
while (used < pool.byteLength) {
 const n = Math.min(4088, pool.byteLength-used);
 const b = Buffer.allocUnsafe(n);
 assert.equal(b.buffer, pool);
 used = b.byteOffset + b.length;
}
await settle();
const before = process.memoryUsage().arrayBuffers;
if (${JSON.stringify(mode)} === 'disabled') disableHostBufferPooling();
if (${JSON.stringify(mode)} === 'explicit') await writeHostProgress('x'.repeat(128)+'\\n');
else await (async () => {
 let encoded = Buffer.from('x'.repeat(128)+'\\n');
 await new Promise((resolve,reject)=>stream.write(encoded,e=>e?reject(e):resolve()));
 encoded = null;
})();
await settle();
const after = process.memoryUsage().arrayBuffers;
assert.equal(keeper.buffer, pool);
const result = {mode:${JSON.stringify(mode)},before,after,extra:after-before};
stream.write(JSON.stringify(result)+'\\n');
`;
		const child = spawnSync(
			process.execPath,
			["--expose-gc", "--import", "tsx", "--input-type=module", "-e", script],
			{ encoding: "utf8" },
		);
		assert.equal(child.status, 0, child.stderr);
		const lines = child.stdout.trim().split("\n");
		const result = JSON.parse(lines[lines.length - 1]);
		assert.equal(result.extra, mode === "pooled" ? 8192 : 0);
	}
});
