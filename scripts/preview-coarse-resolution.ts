// Offline review artifact: selected locations are validation, never routing rules.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { decodeGrid } from "../src/server/coarse-data.server";
import { estimateGrid } from "../src/server/coarse-grid";

const [artifact, output, flag] = process.argv.slice(2);
assert.ok(
	!flag || ["--baseline-v6", "--baseline-v7"].includes(flag),
	"Unknown baseline option",
);
const roadConnections = flag === "--baseline-v6";
const baselineVersion = flag === "--baseline-v7" ? 7 : roadConnections ? 6 : 5;
assert.ok(
	artifact && output,
	"Pass candidate artifact and fresh preview directory",
);
assert.ok(resolve(output).startsWith(`${resolve("data/coarse-quality")}/`));
await mkdir(output);
const raw = await readFile(artifact);
const data = JSON.parse(raw.toString());
const baselineData = JSON.parse(
	await readFile(
		`src/server/data/coarse-grid-v${baselineVersion}.json`,
		"utf8",
	),
);
const baseline = decodeGrid(baselineData);
const candidate = decodeGrid(data);
const scenarios = [];
for (const [name, lat, lon, category] of [
	["Inland", 39.1836, -96.5717, "inland"],
	["Rural", 38.5012, -110.7123, "rural"],
	["Coastal", 32.7765, -79.9311, "coastal"],
	["Mountain", 39.1911, -106.8175, "mountain"],
] as const)
	for (const minutes of [360, 600, 720]) {
		const results = [baseline, candidate].map((grid) => {
			const estimate = estimateGrid(grid, { lat, lon }, minutes);
			return {
				step: grid.step,
				cells: estimate.reachedCells,
				searchMs: estimate.searchMs,
				contourMs: estimate.contourMs,
				geometry: { type: "MultiPolygon", coordinates: estimate.coordinates },
			};
		});
		scenarios.push({ name, category, origin: { lat, lon }, minutes, results });
	}
const report = {
	artifact,
	artifactSha256: createHash("sha256").update(raw).digest("hex"),
	model: data.version,
	baselineModel: baselineData.version,
	roadConnections,
	scenarios,
	scope:
		"Precomputed offline same-query visual comparison. Both geometries use production search/contour code on independently built graphs. Validation locations do not enter routing rules. Cell counts across resolutions are not accuracy measures; no driving references/provider/database calls. Local timing observations only. Basemap uses network independently.",
};
const template = await readFile(
	"scripts/coarse-resolution-preview.html",
	"utf8",
);
await writeFile(
	`${output}/index.html`,
	template.replace(
		"__REPORT_JSON__",
		JSON.stringify(report).replaceAll("<", "\\u003c"),
	),
	{ flag: "wx" },
);
await writeFile(
	`${output}/preview.json`,
	`${JSON.stringify(report, null, 2)}\n`,
	{ flag: "wx" },
);
for (const file of [
	"maplibre-gl.mjs",
	"maplibre-gl-shared.mjs",
	"maplibre-gl-worker.mjs",
	"maplibre-gl.css",
])
	await copyFile(`node_modules/maplibre-gl/dist/${file}`, `${output}/${file}`);
console.log(
	JSON.stringify(
		{
			output,
			artifact,
			artifactSha256: report.artifactSha256,
			scenarios: scenarios.length,
			scope: report.scope,
		},
		null,
		2,
	),
);
