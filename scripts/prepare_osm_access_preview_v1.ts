/** Offline comparison artifact; validation places never enter application routing. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { decodeGrid } from "../src/server/coarse-data.server.ts";
import { estimateGrid } from "../src/server/coarse-grid.ts";

const repo = path.resolve(import.meta.dirname, ".."),
	sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");
const [recipeName, pin] = process.argv.slice(2);
assert.ok(recipeName && pin);
const raw = await readFile(path.resolve(repo, recipeName));
assert.equal(sha(raw), pin);
const plan = JSON.parse(raw.toString("utf8"));
assert.equal(plan.output, "data/coarse-quality/us-osm-car-access-preview-v1");
assert.deepEqual(plan.validationSourceIndexes, [0, 2, 4]);
for (const [name, expected] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
const root = path.join(repo, plan.output);
await mkdir(root);
await writeFile(path.join(root, "execution-plan.json"), raw, { flag: "wx" });
try {
	const started = performance.now(),
		report = JSON.parse(
			(await readFile(path.join(repo, plan.candidateReport))).toString("utf8"),
		);
	const v9raw = await readFile(path.join(repo, plan.v9));
	assert.equal(
		sha(v9raw),
		"28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6",
	);
	const grid = decodeGrid(JSON.parse(v9raw.toString("utf8")));
	const geography = JSON.parse(
		gunzipSync(await readFile(path.join(repo, plan.geography)), {
			maxOutputLength: 1048576,
		}).toString("utf8"),
	);
	const cases = [];
	for (const index of plan.validationSourceIndexes as number[]) {
		const phase = report.phases[index],
			production = phase.productions.find(
				(p: { minutes: number }) => p.minutes === 360,
			);
		assert.ok(production);
		const raw = await readFile(
			path.join(repo, plan.candidateRoot, production.output.filename),
		);
		assert.equal(sha(raw), production.output.sha256);
		const old = estimateGrid(
				grid,
				{ lon: phase.origin[0], lat: phase.origin[1] },
				360,
			),
			label = plan.labels[index];
		assert.ok(label);
		cases.push({
			label,
			origin: phase.origin,
			step: production.frame.step / 1e6,
			old: old.coordinates,
			candidate: JSON.parse(raw.toString("utf8")).coordinates,
		});
	}
	const common = report.commonFiniteComparison;
	const data = {
		cases,
		geography,
		metrics: {
			oldReached: 83,
			newReached: report.overall.candidate.pairedFinite,
			oldMae: common.baseline.meanAbsoluteMinutes,
			newMae: common.candidate.meanAbsoluteMinutes,
			oldP90: common.baseline.p90AbsoluteMinutes,
			newP90: common.candidate.p90AbsoluteMinutes,
		},
	};
	const template = await readFile(path.join(repo, plan.template), "utf8"),
		html = template.replace(
			"__PREVIEW_DATA__",
			JSON.stringify(data).replaceAll("<", "\\u003c"),
		);
	assert.ok(
		!html.includes("__PREVIEW_DATA__") && Buffer.byteLength(html) < 8388608,
	);
	await writeFile(path.join(root, "index.html"), html, { flag: "wx" });
	const result = {
		status: "offline_three_case_same_camera_preview_prepared",
		recipeSha256: pin,
		cases: cases.map((c) => ({
			label: c.label,
			origin: c.origin,
			budgetMinutes: 360,
			stepDegrees: c.step,
		})),
		htmlBytes: Buffer.byteLength(html),
		htmlSha256: sha(Buffer.from(html)),
		prepareMs: performance.now() - started,
		scope:
			"Local validation-only visual comparison of three saved source sites. Current v9 queried offline; candidate uses previously sealed outputs. No app/API/DB/env/provider/download/deployment change. Review aid, not nationwide accuracy or full app/shared-camera admission.",
	};
	await writeFile(
		path.join(root, "report.json"),
		`${JSON.stringify(result, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(`${JSON.stringify(result)}\n`);
} catch (error) {
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error) }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
