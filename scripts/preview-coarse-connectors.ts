// Review failed and improved validation cases; no routing rules or service calls.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { gunzipSync } from "node:zlib";

const [evaluation, output] = process.argv.slice(2);
assert.ok(
	evaluation &&
		output &&
		resolve(output).startsWith(`${resolve("data/coarse-quality")}/`),
);
const report = JSON.parse(
	await readFile(join(evaluation, "comparison.json"), "utf8"),
);
const pathBytes = await readFile(join(evaluation, "paths.json.gz"));
assert.equal(
	createHash("sha256").update(pathBytes).digest("hex"),
	report.pathSha256,
);
const paths = JSON.parse(gunzipSync(pathBytes).toString()) as Array<{
	id: string;
	model: string;
	nodes: number[][];
}>;
type Row = {
	id: string;
	set: string;
	baseline: { pointMinutes: number };
	candidate: { pointMinutes: number };
	referenceMinutes: number;
	absoluteErrorChangeMinutes: number;
};
const rows = report.rows as Row[];
const frontier = rows
	.filter((r) => r.set === "frontier")
	.sort((a, b) => a.absoluteErrorChangeMinutes - b.absoluteErrorChangeMinutes);
const regional = rows
	.filter((r) => r.set !== "frontier")
	.sort((a, b) => b.absoluteErrorChangeMinutes - a.absoluteErrorChangeMinutes);
const selected = [frontier[0], frontier[frontier.length - 1], regional[0]];
const references = new Map<string, number[][]>();
for (const [folder, prefix] of [
	["coarse-frontier-reference-2026-10-23", "frontier/"],
	["coarse-control-reference-2026-10-24", ""],
	["coarse-benchmark-reference-2026-10-24", ""],
]) {
	const base = `docs/evidence/${folder}/reference`;
	const plan = JSON.parse(await readFile(`${base}/plan.json`, "utf8"));
	const manifest = JSON.parse(await readFile(`${base}/sha256.json`, "utf8"));
	for (let i = 0; i < plan.queries.length; i++) {
		const name = `${String(i).padStart(2, "0")}-response.txt`;
		const bytes = await readFile(`${base}/${name}`);
		assert.equal(
			createHash("sha256").update(bytes).digest("hex"),
			manifest[name],
		);
		references.set(
			prefix + plan.queries[i].id,
			JSON.parse(bytes.toString()).features[0].geometry.coordinates,
		);
	}
}
assert.equal(references.size, 83);
const scenarios = [];
for (const row of selected) {
	const reference = references.get(`${row.set}/${row.id}`);
	assert.ok(reference);
	const getPath = (model: string) => {
		const path = paths.find(
			(p) => p.id === `${row.set}/${row.id}` && p.model === model,
		);
		assert.ok(path);
		return path.nodes;
	};
	scenarios.push({
		...row,
		referenceEngine: "ORS9.10.0",
		paths: [getPath("v8"), getPath("candidate"), reference],
	});
}
await mkdir(output);
let template = await readFile(
	"scripts/coarse-calibration-preview.html",
	"utf8",
);
template = template
	.replaceAll("Class timing candidate", "Connector timing candidate")
	.replace("Road-class timing experiment", "Connector timing experiment")
	.replace(
		"105→95 and 80→85 km/h source classes. Geometry and 25 km/h local costs stay fixed.",
		"NE artificial connections: 55 km/h. Major roads: 105; secondary: 85; Census/local: 25. Geometry stays fixed.",
	)
	.replace("and retained Valhalla/OpenStreetMap", "")
	.replace(
		"Reference engines and datasets differ;",
		"All shown references use the matched ORS 9.10 cohort;",
	);
await writeFile(
	join(output, "index.html"),
	template.replace(
		"__REPORT_JSON__",
		JSON.stringify({
			scenarios,
			accuracyGatesPassed: report.accuracyGatesPassed,
		}).replaceAll("<", "\\u003c"),
	),
	{ flag: "wx" },
);
await writeFile(
	join(output, "preview.json"),
	`${JSON.stringify({ scenarios, accuracyGatesPassed: report.accuracyGatesPassed }, null, 2)}\n`,
	{ flag: "wx" },
);
for (const name of [
	"maplibre-gl.mjs",
	"maplibre-gl-shared.mjs",
	"maplibre-gl-worker.mjs",
	"maplibre-gl.css",
])
	await copyFile(`node_modules/maplibre-gl/dist/${name}`, join(output, name));
console.log(
	JSON.stringify({
		output,
		scenarios: scenarios.map((s) => s.id),
		providerRequests: 0,
	}),
);
