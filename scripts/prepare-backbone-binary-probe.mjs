// Creates one isolated, env-free packaging experiment; never changes the active app.
import assert from "node:assert/strict";
import {
	copyFile,
	cp,
	mkdir,
	readFile,
	symlink,
	writeFile,
} from "node:fs/promises";
import { join, resolve } from "node:path";
import { encodeContainer, sha256 } from "./backbone-binary-format.mjs";

const planPath = "docs/evidence/coarse-backbone-binary-2026-10-25/plan.json";
const planSha256 =
	"8d7ff6a94127d1b2a87d0f039b4de11de189e9c688d4d5a550dfc6b9722c158a";
const [output] = process.argv.slice(2);
assert.ok(
	output && resolve(output).startsWith(`${resolve("data/coarse-quality")}/`),
);
const planRaw = await readFile(planPath);
assert.equal(sha256(planRaw), planSha256);
const plan = JSON.parse(planRaw);
for (const [path, hash] of Object.entries({
	...plan.inputs,
	...plan.runtimeArrayInputs,
}))
	assert.equal(sha256(await readFile(path)), hash, path);
const report = JSON.parse(
	await readFile(
		"docs/evidence/coarse-backbone-geometry-2026-10-25/report.json",
		"utf8",
	),
);
const raw = await readFile("src/server/data/coarse-grid-v9.json");
const kept = JSON.parse(raw);
assert.equal(
	sha256(raw),
	"28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6",
);
delete kept.roadLayer;
delete kept.supplementalRoadVisits;
const entries = [];
for (const [name, info] of Object.entries(report.packedArrays))
	entries.push({
		name,
		gzip: await readFile(info.path),
		gzipSha256: info.sha256,
		rawSha256: info.rawSha256,
		rawBytes: info.rawBytes,
		elements: info.elements,
		typecode: info.typecode,
	});
const packed = encodeContainer(kept, entries, {
	nodes: report.nodes,
	arcs: report.arcs,
	originalNodes: report.originalNodes,
	parts: report.counts.uniqueParts,
	sourceGraphReportSha256: sha256(
		await readFile(
			"docs/evidence/coarse-backbone-geometry-2026-10-25/report.json",
		),
	),
});
assert.equal(
	packed.descriptor.entries.filter((entry) => entry.kind === "graph").length,
	17,
);
assert.equal(
	packed.descriptor.entries.filter((entry) => entry.kind === "kept").length,
	12,
);
await mkdir(output); // Existing success/failure directories are never overwritten.
await cp("src", join(output, "src"), {
	recursive: true,
	filter: (path) =>
		!path.endsWith(".test.ts") && resolve(path) !== resolve("src/server/data"),
});
await mkdir(join(output, "src/server/data"));
await cp("public", join(output, "public"), { recursive: true });
for (const file of ["package.json", "package-lock.json", "tsconfig.json"])
	await copyFile(file, join(output, file));
await symlink(resolve("node_modules"), join(output, "node_modules"), "dir");
await mkdir(join(output, "probe"));
const tools = [
	"backbone-binary-asset.mjs",
	"backbone-binary-format.mjs",
	"backbone-binary-validate.mjs",
	"backbone-binary-loader.mjs",
];
for (const tool of tools)
	await copyFile(`scripts/${tool}`, join(output, "probe", tool));
await writeFile(join(output, "probe/backbone.bin"), packed.bytes, {
	flag: "wx",
});
const expected = {
	sha256: sha256(packed.bytes),
	bytes: packed.bytes.length,
	planSha256,
};
await writeFile(
	join(output, "probe/manifest.json"),
	`${JSON.stringify(expected, null, 2)}\n`,
	{ flag: "wx" },
);
await writeFile(
	join(output, "src/server/coarse-estimate.server.ts"),
	`
export function getEstimateConfig() {
 return Response.json({ provider:"coarse",configured:false,health:"unconfigured",minMinutes:30,maxMinutes:720,
 engineVersion:"backbone-packaging-probe",graphVersion:"none",coverage:"No routing model active in this isolated probe.",
 healthMessage:"Data-load diagnostics only; contours unavailable." },{headers:{"Cache-Control":"no-store"}});
}
export function runEstimate(_request:Request) {
 return Response.json({error:"Contours unavailable in the isolated binary packaging probe."},{status:503});
}
`,
);
await writeFile(
	join(output, "probe/handler.mjs"),
	`
import binaryUrl from "#geo-backbone-binary";
import expected from "./manifest.json";
import { loadBackboneBinary } from "./backbone-binary-loader.mjs";
import { decodeGrid } from "../src/server/coarse-data.server.ts";
let state;
let loads = 0;
export default function() {
 if (!state) { state = loadBackboneBinary(binaryUrl,expected,decodeGrid); loads++; }
 const retainedGraphBytes = Object.values(state.graph).reduce((sum,values)=>sum+values.byteLength,0);
 return Response.json({...state.summary,loads,retainedGraphBytes,
 baseLandBytes:state.base.land.byteLength,baseRoadVisits:state.base.roadVisits?.size??0},
 {headers:{"Cache-Control":"no-store"}});
}
`,
);
const config = await readFile("vite.config.ts", "utf8");
assert.ok(config.includes("nitro()"));
await writeFile(
	join(output, "vite.config.ts"),
	`import { resolve } from "node:path";\nimport { backboneBinaryAsset } from "./probe/backbone-binary-asset.mjs";\n${config}`.replace(
		"nitro()",
		`nitro({
 handlers:[{route:"/api/backbone-probe",method:"get",handler:resolve("probe/handler.mjs")}],
 hooks:{"rollup:before":(_nitro,bundle)=>{
 if(!Array.isArray(bundle.plugins))throw new Error("Expected final bundler plugin array");
 bundle.plugins.unshift(backboneBinaryAsset(resolve("probe/backbone.bin")));
 }}
 })`,
	),
);
await writeFile(
	join(output, "probe/backbone-binary-asset.d.mts"),
	`export declare function backboneBinaryAsset(path:string): import("rolldown").Plugin;\n`,
);
const sourceFiles = [
	"scripts/prepare-backbone-binary-probe.mjs",
	...tools.map((name) => `scripts/${name}`),
];
const toolSources = {};
for (const name of sourceFiles)
	toolSources[name] = sha256(await readFile(name));
const record = {
	output,
	planSha256,
	container: expected,
	graphArrayCount: 17,
	keptBlobCount: 12,
	keptJsonSha256: packed.descriptor.keptJsonSha256,
	entries: packed.descriptor.entries,
	toolSources,
	dataAssetName: "server-data/backbone.bin",
	routingAvailable: false,
	scope:
		"Single immutable binary asset in an isolated env-free existing-app copy; ordinary and Vercel builds still pending. No active app, source geometry, cost, routing/query, DB, dependency or deployment change.",
};
await writeFile(
	join(output, "probe.json"),
	`${JSON.stringify(record, null, 2)}\n`,
	{ flag: "wx" },
);
console.log(
	JSON.stringify(
		{
			output,
			containerBytes: expected.bytes,
			sha256: expected.sha256,
			graphArrays: 17,
			keptBlobs: 12,
			planSha256,
			routingAvailable: false,
		},
		null,
		2,
	),
);
