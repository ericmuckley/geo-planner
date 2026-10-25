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
const plan = JSON.parse(
	await readFile(
		"docs/evidence/coarse-holdout-plan-2026-10-23/plan.json",
		"utf8",
	),
);
const original = JSON.parse(
	await readFile(
		"docs/evidence/coarse-quality-2026-10-22/comparison.json",
		"utf8",
	),
);
function decodeShape(encoded: string) {
	let index = 0,
		lat = 0,
		lon = 0;
	const points: number[][] = [];
	function component() {
		let value = 0,
			shift = 0,
			byte: number;
		do {
			assert.ok(index < encoded.length && shift < 32);
			byte = encoded.charCodeAt(index++) - 63;
			value |= (byte & 31) << shift;
			shift += 5;
		} while (byte >= 32);
		return value & 1 ? ~(value >>> 1) : value >>> 1;
	}
	while (index < encoded.length) {
		lat += component();
		lon += component();
		points.push([lon / 1e6, lat / 1e6]);
	}
	return points;
}
const scenarios = [];
for (const row of selected) {
	let reference: number[][];
	if (row.set === "frontier") {
		const i = plan.queries.findIndex((q: { id: string }) => q.id === row.id);
		assert.ok(i >= 0);
		const raw = JSON.parse(
			await readFile(
				`docs/evidence/coarse-frontier-reference-2026-10-23/reference/${String(i).padStart(2, "0")}-response.txt`,
				"utf8",
			),
		);
		reference = raw.features[0].geometry.coordinates;
	} else {
		const trip =
			row.set === "original"
				? original.samples.find((r: { name: string }) => r.name === row.id)
						.reference.trip
				: JSON.parse(
						await readFile(
							`docs/evidence/coarse-regional-2026-10-22/reference/${row.id}.json`,
							"utf8",
						),
					).body.trip;
		reference = trip.legs.flatMap((leg: { shape: string }) =>
			decodeShape(leg.shape),
		);
	}
	const getPath = (model: string) => {
		const path = paths.find(
			(p) => p.id === `${row.set}/${row.id}` && p.model === model,
		);
		assert.ok(path);
		return path.nodes;
	};
	scenarios.push({
		...row,
		referenceEngine: row.set === "frontier" ? "ORS9.10.0" : "Valhalla3.9.1",
		paths: [getPath("v8"), getPath("candidate"), reference],
	});
}
await mkdir(output);
const template = await readFile(
	"scripts/coarse-calibration-preview.html",
	"utf8",
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
