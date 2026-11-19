/** Compare every saved production map without executing either routing model. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import { type TimingRow, timingSummary } from "./coarse-damped-gates.ts";

type Asset = { filename: string; bytes: number; sha256: string };
type Production = { minutes: number; frame: { step: number }; output: Asset };
type Report = {
	rows: (TimingRow & { id: string })[];
	phases: { origin: [number, number]; productions: Production[] }[];
	gates: Record<string, boolean>;
};

const began = performance.now();
const repo = path.resolve(import.meta.dirname, "..");
const sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");
const [recipe, pin] = process.argv.slice(2);
assert.ok(recipe && pin);
const encoded = await readFile(path.resolve(repo, recipe));
assert.equal(sha(encoded), pin);
const plan = JSON.parse(encoded.toString("utf8"));
assert.equal(
	plan.output,
	"data/coarse-quality/us-osm-display-refinement-preview-v1",
);
assert.equal(plan.hostSeconds, 300);
assert.equal(plan.maxOwnedBytes, 134217728);
assert.ok(
	plan.priorReserveBytes +
		plan.newClosedAllocationBytes +
		plan.metadataScratchReserveBytes +
		plan.maxOwnedBytes <
		72 * 1024 ** 3,
);
for (const [name, expected] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
const root = path.join(repo, plan.output);
await mkdir(root);
await writeFile(path.join(root, "execution-plan.json"), encoded, {
	flag: "wx",
});
const load = async (name: string) =>
	JSON.parse(await readFile(path.join(repo, name), "utf8"));
const check = () => {
	assert.ok(performance.now() - began < 300000, "Preview preparation deadline");
	assert.ok(process.memoryUsage().rss < 1024 ** 3, "Preview preparation RSS");
};
let providerRequests = 0;
globalThis.fetch = async () => {
	providerRequests++;
	throw new Error("Unexpected outbound request");
};

try {
	const before = (await load(plan.beforeReport)) as Report;
	const after = (await load(plan.afterReport)) as Report;
	assert.equal(before.phases.length, 21);
	assert.equal(after.phases.length, 21);
	assert.equal(before.rows.length, 83);
	assert.equal(after.rows.length, 83);
	assert.deepEqual(
		before.rows.map((r) => r.id).sort(),
		after.rows.map((r) => r.id).sort(),
	);
	const geography = await loadOriginGeography(
		path.join(repo, plan.geographySource),
		plan.geographyManifestSha256,
	);
	const polygons = async (source: string, asset: Asset) => {
		assert.match(asset.filename, /^origin-\d{2}-\d+\.geojson$/);
		const raw = await readFile(path.join(repo, source, asset.filename));
		assert.equal(raw.length, asset.bytes);
		assert.ok(raw.length <= 3000000);
		assert.equal(sha(raw), asset.sha256);
		const shape = JSON.parse(raw.toString("utf8"));
		assert.equal(shape.type, "MultiPolygon");
		return shape.coordinates;
	};
	const cases = [];
	for (const [index, oldPhase] of before.phases.entries()) {
		const newPhase = after.phases[index];
		assert.deepEqual(newPhase.origin, oldPhase.origin);
		assert.deepEqual(
			newPhase.productions.map((p) => p.minutes),
			oldPhase.productions.map((p) => p.minutes),
		);
		for (const [j, old] of oldPhase.productions.entries()) {
			check();
			const next = newPhase.productions[j];
			cases.push({
				label: `${oldPhase.origin.map((v) => v.toFixed(4)).join(", ")} · ${old.minutes / 60} h`,
				origin: oldPhase.origin,
				minutes: old.minutes,
				oldStep: old.frame.step / 1e6,
				step: next.frame.step / 1e6,
				old: await polygons(plan.beforeRoot, old.output),
				candidate: await polygons(plan.afterRoot, next.output),
			});
		}
	}
	assert.equal(cases.length, 37);
	const byId = new Map(after.rows.map((r) => [r.id, r]));
	const available = before.rows.filter(
		(r) =>
			r.candidate.pointMinutes !== null &&
			byId.get(r.id)?.candidate.pointMinutes !== null,
	);
	assert.ok(available.length > 0);
	const oldSummary = timingSummary(available, "candidate");
	const nextSummary = timingSummary(
		available.map((r) => {
			const next = byId.get(r.id);
			assert.ok(next);
			return next;
		}),
		"candidate",
	);
	const metrics = {
		commonCases: available.length,
		oldReached: before.rows.filter((r) => r.candidate.pointMinutes !== null)
			.length,
		newReached: after.rows.filter((r) => r.candidate.pointMinutes !== null)
			.length,
		oldMae: oldSummary.meanAbsoluteMinutes,
		newMae: nextSummary.meanAbsoluteMinutes,
		oldP90: oldSummary.p90AbsoluteMinutes,
		newP90: nextSummary.p90AbsoluteMinutes,
		oldFailedGates: Object.entries(before.gates)
			.filter(([, passed]) => !passed)
			.map(([name]) => name),
		newFailedGates: Object.entries(after.gates)
			.filter(([, passed]) => !passed)
			.map(([name]) => name),
	};
	const template = await readFile(path.join(repo, plan.template), "utf8");
	const html = template.replace(
		"__PREVIEW_DATA__",
		JSON.stringify({
			cases,
			geography: geography.geography,
			metrics,
		}).replaceAll("<", "\\u003c"),
	);
	assert.ok(
		!html.includes("__PREVIEW_DATA__") && Buffer.byteLength(html) < 67108864,
	);
	await writeFile(path.join(root, "index.html"), html, { flag: "wx" });
	check();
	assert.equal(providerRequests, 0);
	const result = {
		status: "all37_saved_production_display_comparisons_prepared",
		recipeSha256: pin,
		cases: cases.map((c) => ({
			origin: c.origin,
			minutes: c.minutes,
			oldStep: c.oldStep,
			step: c.step,
		})),
		metrics,
		htmlBytes: Buffer.byteLength(html),
		htmlSha256: sha(Buffer.from(html)),
		providerRequests,
		modelQueries: 0,
		hostTotalMsIncludingBindingsMapReadsVerificationHTMLAndIO:
			performance.now() - began,
		scope:
			"Read-only local review of every37saved production map pair with a shared camera. All83availability cases retained; errors use identical finite cases. No model/native/PBF/provider/DB/app/env/dependency/deployment change. This artifact does not establish area/nationwide accuracy or pass path/source/shore/app/API/camera admission.",
	};
	await writeFile(
		path.join(root, "report.json"),
		`${JSON.stringify(result, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(
		`${JSON.stringify({ status: result.status, cases: cases.length, htmlBytes: result.htmlBytes })}\n`,
	);
} catch (error) {
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error), stack: error instanceof Error ? error.stack : null, hostTotalMs: performance.now() - began }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
