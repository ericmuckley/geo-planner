// Offline validation fixtures only; never imported by the application.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { z } from "zod";
import { readControlPlan, replayControlRun } from "./coarse-control";
import { readFrozenPlan, replayReferenceRun } from "./coarse-holdout";

export const planPath =
	"docs/evidence/coarse-benchmark-plan-2026-10-24/plan.json";
export const planSha256 =
	"77d357142dfe266274c3dc6693732963b296e027888b036725f70b27d5401a93";
export const sourceHashes = {
	"docs/evidence/coarse-class-calibration-2026-10-23/comparison.json":
		"cb31b7f281a737afe6b19d4e8410f533de2ddd7832f552602944a81e376b07ba",
	"docs/evidence/coarse-control-reference-2026-10-24/comparison.json":
		"6b9c0278e41c9c11b6eee8dc5104f4aba36393dcddb108caa8467c062caebb2b",
	"docs/evidence/coarse-frontier-reference-2026-10-23/comparison.json":
		"ea9ece78749832afee47c07a6b6359799dc6c97fcd6899292c405967bcce316c",
	"docs/evidence/coarse-control-reference-2026-10-24/reference/sha256.json":
		"65966b8de287ee8b424b7720f79df8d7135df25b51427237825fbfc2116eb5d7",
	"docs/evidence/coarse-frontier-reference-2026-10-23/reference/sha256.json":
		"09d38037f943bb303175feeb8604a90d1ae4061d585f3ebb413edd1ee47194eb",
	"docs/evidence/coarse-quality-2026-10-22/comparison.json":
		"90dce82c094f41c13de37065ca677650ecc3fe36187008379bcc48950470c96c",
	"docs/evidence/coarse-regional-2026-10-22/comparison.json":
		"acb588585be88a4d2adfd64028fff8fb462325054c989c70cf0a757f31bd782c",
};
const json = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`;
const position = z.object({
	lon: z.number().finite(),
	lat: z.number().finite(),
});
const model = z.object({
	pointMinutes: z.number().finite().nonnegative(),
	cellMinutes: z.number().finite().nonnegative(),
	predictedReachable: z.boolean(),
});
const rowSchema = z.object({
	id: z.string(),
	set: z.enum(["frontier", "original", "regional"]),
	origin: position,
	destination: position,
	budgetMinutes: z.number().positive(),
	referenceMinutes: z.number().positive(),
	baseline: model,
	candidate: model,
});
export type BenchmarkModelRow = z.infer<typeof rowSchema>;

/** Reconstruct the fixed complement and validate every reused result offline. */
export async function buildBenchmarkPlan() {
	const sources: Record<string, unknown> = {};
	for (const [path, expected] of Object.entries(sourceHashes)) {
		const bytes = await readFile(path);
		assert.equal(createHash("sha256").update(bytes).digest("hex"), expected);
		sources[path] = JSON.parse(bytes.toString());
	}
	const paths = Object.keys(sourceHashes);
	const calibration = z
		.object({ rows: z.array(rowSchema).length(83) })
		.parse(sources[paths[0]]);
	const control = await replayControlRun(
		"docs/evidence/coarse-control-reference-2026-10-24/reference",
	);
	const frontier = await replayReferenceRun(
		"docs/evidence/coarse-frontier-reference-2026-10-23/reference",
	);
	assert.deepEqual(control, sources[paths[1]]);
	assert.deepEqual(frontier, sources[paths[2]]);
	assert.equal(control.transport, "live");
	assert.equal(control.overall.pairedFinite, 6);
	assert.equal(frontier.overall.pairedFinite, 48);
	const [controlPlan, frontierPlan] = await Promise.all([
		readControlPlan(),
		readFrozenPlan(),
	]);
	const oldSample = z.object({
		id: z.string().optional(),
		name: z.string().optional(),
		origin: position.optional(),
		destination: position,
		referenceMinutes: z.number().positive(),
		referenceKm: z.number().positive(),
	});
	const oldSets = [5, 6].map((i) =>
		z
			.object({ origin: position.optional(), samples: z.array(oldSample) })
			.parse(sources[paths[i]]),
	);
	const records = calibration.rows.map((row) => {
		const id = `${row.set}/${row.id}`;
		const coordinates = [
			[row.origin.lon, row.origin.lat],
			[row.destination.lon, row.destination.lat],
		];
		const request = {
			coordinates,
			instructions: false,
			preference: "fastest",
			radiuses: [350, 350],
			options: { avoid_borders: "all", avoid_features: ["ferries"] },
		};
		let valhalla: { minutes: number; distanceKm: number } | null = null;
		if (row.set === "frontier") {
			const frozen = frontierPlan.queries.find((q) => q.id === row.id);
			const saved = frontier.cases.find((q) => q.id === row.id);
			assert.ok(frozen && saved?.reference);
			assert.deepEqual(request, frozen.request);
			assert.equal(row.baseline.pointMinutes, frozen.modelPointMinutes);
			assert.equal(
				row.baseline.predictedReachable,
				frozen.expectedMapReachable,
			);
			assert.equal(row.budgetMinutes, frozen.budgetMinutes);
			assert.equal(row.referenceMinutes, saved.reference.minutes);
		} else {
			const set = oldSets[row.set === "original" ? 0 : 1];
			const old = set.samples.find((r) => (r.id ?? r.name) === row.id);
			assert.ok(old);
			assert.deepEqual(old.destination, row.destination);
			assert.deepEqual(set.origin ?? old.origin, row.origin);
			assert.equal(old.referenceMinutes, row.referenceMinutes);
			valhalla = { minutes: old.referenceMinutes, distanceKm: old.referenceKm };
		}
		const reused = controlPlan.queries.find((q) => q.id === id);
		if (reused) {
			assert.deepEqual(reused.request, request);
			assert.equal(reused.v8Minutes, row.baseline.pointMinutes);
		}
		return { ...row, id, request, valhalla };
	});
	assert.equal(new Set(records.map((r) => r.id)).size, 83);
	assert.equal(
		new Set(records.map((r) => JSON.stringify(r.request.coordinates))).size,
		83,
	);
	const reusedIds = [
		...control.cases.map((r) => r.id),
		...frontier.cases.map((r) => `frontier/${r.id}`),
	];
	assert.equal(new Set(reusedIds).size, 54);
	assert.ok(reusedIds.every((id) => records.some((r) => r.id === id)));
	const remaining = records
		.filter((r) => !reusedIds.includes(r.id))
		.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
	assert.equal(remaining.length, 29);
	assert.ok(remaining.every((r) => r.valhalla !== null));
	const plan = {
		version: 1,
		status: "prepared offline; new 29-request budget not authorized",
		selection:
			"Exact set/id-sorted complement of all35 old OD pairs minus saved6; reuse all48 frontier results. No query replacement or routing exceptions.",
		inputs: sourceHashes,
		reference: {
			endpoint:
				"https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson",
			maximumRequests: 29,
			minimumIntervalMs: 6500,
			timeoutMs: 45000,
			maximumBodyBytes: 2_000_000,
			retries: 0,
			paidSpendCapEuro: 0,
			stopOnStatus: [401, 403, 429],
		},
		reuse: {
			control: control.cases.map((r) => r.id),
			frontier: frontier.cases.map((r) => `frontier/${r.id}`),
		},
		queries: remaining.map((r) => ({
			id: r.id,
			existingValhallaMinutes: r.valhalla?.minutes,
			existingValhallaKm: r.valhalla?.distanceKm,
			v8Minutes: r.baseline.pointMinutes,
			request: r.request,
		})),
		reportPolicy: {
			planned: { original: 11, regional: 24, frontier: 48, total: 83 },
			signedDifference:
				"Model minus ORS; percentage divides by ORS minutes. Older-route ORS minus Valhalla is reported separately.",
			metrics:
				"All83 case ledger, signed/absolute/percentage differences, MAE/median/p90 nearest-rank, v8/candidate gains/regressions, sets, frontier horizons and origin groups; no combined mean can replace a failing group.",
			quality:
				"Snap>100m remains primary with a separately denominated <=100m sensitivity. Preserve all missing/error/skipped cases; no replacements.",
			versions:
				"Always stratify by full engine/build/graph/OSM metadata. Pooled primary summaries require all83 finite with complete identical metadata matching saved references. Any mismatch/missing metadata leaves primary null; report cohorts and every case instead.",
			interpretation:
				"Observed development benchmark only, not traffic truth, nationwide/area accuracy or a fresh holdout. Compare saved candidate descriptively; original rejection/gates stay unchanged. No new model acceptance policy or correction is selected; preregister any future candidate/gates before producing it.",
			synthetic:
				"Injected transport is labeled synthetic; mixed saved-live/synthetic reports never qualify as a completed live benchmark.",
		},
	};
	return { plan, records, control, frontier };
}

export async function readBenchmarkPlan() {
	const raw = await readFile(planPath, "utf8");
	assert.equal(createHash("sha256").update(raw).digest("hex"), planSha256);
	const inputs = await buildBenchmarkPlan();
	assert.equal(raw, json(inputs.plan), "Frozen benchmark plan changed");
	return { ...inputs, raw, queries: inputs.plan.queries };
}
