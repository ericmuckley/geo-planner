/** Finer-grid capacity pilot selected by highest saved queue pressure; no score. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import type { PointTiming } from "./coarse_osm_access_timing_v2.ts";
import {
	finishAccessPointTiming,
	type PreparedPointTiming,
	prepareAccessPointTiming,
} from "./coarse_osm_access_timing_v3.ts";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import { settledPhaseMemory } from "./coarse_osm_phase_lifetime_v1.ts";
import { reusedContextDisplay } from "./coarse_osm_reused_display_v2.ts";
import { waterRoutingGeographyV6 } from "./coarse_osm_routing_geography_v6.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";

const began = performance.now();
const repo = path.resolve(import.meta.dirname, "..");
const sha = (bytes: Uint8Array | string) =>
	createHash("sha256").update(bytes).digest("hex");
const xy = (place: { lon: number; lat: number }): Coordinate => [
	place.lon,
	place.lat,
];
const key = (point: Coordinate) => JSON.stringify(point);
const loadJson = async (name: string) =>
	JSON.parse(await readFile(path.join(repo, name), "utf8"));
const [recipe, pin] = process.argv.slice(2);
assert.ok(recipe && pin && global.gc);
const encoded = await readFile(path.resolve(repo, recipe));
assert.equal(sha(encoded), pin);
const plan = JSON.parse(encoded.toString("utf8"));
assert.equal(
	plan.output,
	"data/coarse-quality/us-osm-finer-display-capacity-pilot-v2",
);
assert.deepEqual(plan.originIndices, [4]);
assert.ok(
	plan.priorReserveBytes +
		plan.newClosedAllocationBytes +
		plan.metadataScratchReserveBytes +
		plan.maxOwnedBytes <
		72 * 1024 ** 3,
);
for (const [name, pin] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, name))), pin, name);
const root = path.join(repo, plan.output);
await mkdir(root);
await writeFile(path.join(root, "execution-plan.json"), encoded, {
	flag: "wx",
});

let requests = 0;
globalThis.fetch = async () => {
	requests++;
	throw new Error("Unexpected outbound request");
};
const check = () => {
	assert.ok(
		performance.now() - began < 900000,
		"Finer capacity pilot deadline",
	);
	assert.ok(
		process.memoryUsage().rss < 4 * 1024 ** 3,
		"Finer capacity pilot RSS",
	);
};
let activeMinutes: number | null = null;
let lastObservedQueryArrayBuffers = 0;
let immutableSeedingChecked = false;
let heldArrayBuffers: number | null = null;
const queryBuffers: WeakRef<ArrayBufferLike>[] = [];
try {
	const parity = await loadJson(plan.parityReport);
	assert.equal(
		parity.status,
		"all_saved_origins_reused_display_same_resolution_parity_complete",
	);
	assert.equal(parity.displays, 58);
	assert.equal(parity.diagnosticPointCases, 83);
	const candidate = await loadJson(plan.candidate);
	const peaks = candidate.phases.map(
		(phase: {
			diagnostic: { stats: { maximumHeapEntries: number } };
			productions: { stats: { maximumHeapEntries: number } }[];
		}) =>
			Math.max(
				...[phase.diagnostic, ...phase.productions].map(
					(p) => p.stats.maximumHeapEntries,
				),
			),
	);
	const originIndex = peaks.indexOf(Math.max(...peaks));
	assert.equal(originIndex, 4);
	const phase = candidate.phases[originIndex];
	const samples = candidate.rows.filter(
		(row: { origin: { lon: number; lat: number } }) =>
			key(xy(row.origin)) === key(phase.origin),
	);
	const records = (await loadJson(plan.connections)) as {
		coordinate: Coordinate;
		connection: OriginConnection | null;
	}[];
	const connections = new Map(
		records.map((row) => [key(row.coordinate), row.connection]),
	);
	const source = connections.get(key(phase.origin));
	assert.ok(source);
	const access = await loadJson(plan.accessReport);
	const asset = access.rows.find(
		(row: { coordinate: Coordinate }) =>
			key(row.coordinate) === key(phase.origin),
	).output;
	const compressed = readFileSync(
		path.join(repo, plan.accessSource, asset.filename),
	);
	assert.equal(sha(compressed), asset.sha256);
	assert.equal(compressed.length, asset.compressedBytes);
	const raw = gunzipSync(compressed);
	assert.equal(sha(raw), asset.rawSha256);
	assert.equal(raw.length, asset.rawBytes);
	const choices = JSON.parse(raw.toString("utf8")) as OriginConnection[];
	const starts = accessStarts(source, choices);
	const baseline = await settledPhaseMemory();
	const core = await loadPackedCar(
		path.join(repo, plan.coreSource),
		plan.coreManifestSha256,
		check,
	);
	const paid = await loadPaidGeometry(
		path.join(repo, plan.geometrySource),
		plan.geometryManifestSha256,
		core.graph,
		check,
	);
	const history = await loadTurnContexts(
		path.join(repo, plan.contextSource),
		plan.contextManifestSha256,
		path.join(repo, plan.coreSource),
		plan.coreManifestSha256,
		core.graph,
		check,
	);
	const coarse = await loadOriginGeography(
		path.join(repo, plan.geographySource),
		plan.geographyManifestSha256,
	);
	const packet = await loadWaterRasterV2(
		path.join(repo, plan.waterSource),
		plan.waterManifestSha256,
	);
	const geography = waterRoutingGeographyV6(coarse.geography, packet);
	const afterLoad = await settledPhaseMemory();
	heldArrayBuffers = afterLoad.arrayBuffers;
	const held = afterLoad.arrayBuffers - baseline.arrayBuffers;
	assert.ok(held <= 162238546);
	const specs = [
		{ minutes: 900, expected: phase.diagnostic, diagnostic: true },
		...phase.productions.map((p: { minutes: number }) => ({
			minutes: p.minutes,
			expected: p,
			diagnostic: false,
		})),
	];
	assert.equal(specs.length, 4);
	const results = [];
	for (const spec of specs) {
		activeMinutes = spec.minutes;
		immutableSeedingChecked = false;
		check();
		let prepared: PreparedPointTiming[] = [];
		const timings: Record<string, PointTiming> = {};
		let fingerprints: string[] = [];
		let observations = 0,
			maxObservedQueryArrayBuffers = 0;
		const runBegan = performance.now();
		const result = reusedContextDisplay(
			core.graph,
			paid.geometry,
			history.contexts,
			geography,
			source,
			starts,
			{
				maxTicks: spec.minutes * 60 * 8,
				maxCells: 33554432,
				check,
				beforeSeed: (field) => {
					fingerprints = [
						sha(new Uint8Array(field.labels.buffer)),
						sha(new Uint8Array(field.vertexArrivalSeconds.buffer)),
					];
					if (spec.diagnostic)
						prepared = samples.map(
							(sample: { destination: { lon: number; lat: number } }) =>
								prepareAccessPointTiming(
									core.graph,
									paid.geometry,
									field,
									source.origin,
									xy(sample.destination),
									connections.get(key(xy(sample.destination))) ?? null,
								),
						);
				},
				observeBacking: (buffers) => {
					queryBuffers.push(...buffers.map((b) => new WeakRef(b)));
					const extra =
						process.memoryUsage().arrayBuffers - afterLoad.arrayBuffers;
					lastObservedQueryArrayBuffers = extra;
					maxObservedQueryArrayBuffers = Math.max(
						maxObservedQueryArrayBuffers,
						extra,
					);
					assert.ok(extra <= 67108864, "Observed query backing cap");
					if (observations++ === 0) {
						assert.deepEqual(
							buffers.slice(0, 2).map((b) => sha(new Uint8Array(b))),
							fingerprints,
							"Road seeding changed query labels",
						);
						immutableSeedingChecked = true;
					}
				},
				probe: (grid) => {
					if (spec.diagnostic)
						for (let i = 0; i < samples.length; i++)
							timings[samples[i].id] = finishAccessPointTiming(
								geography,
								grid,
								prepared[i],
							);
				},
			},
			spec.diagnostic,
		);
		assert.equal(observations, 2);
		assert.ok(result.frame.step >= 5000 && result.frame.step <= 25000);
		assert.deepEqual(result.fieldStats, spec.expected.fieldStats);
		if (spec.diagnostic)
			for (const sample of samples)
				assert.equal(
					timings[sample.id].roadTicks,
					spec.expected.timings[sample.id].roadTicks,
				);
		const json = JSON.stringify(result.output);
		await settledPhaseMemory();
		const released = await settledPhaseMemory();
		assert.equal(
			released.arrayBuffers,
			afterLoad.arrayBuffers,
			"Query owner backing restored",
		);
		const filename = spec.expected.output.filename;
		assert.equal(
			filename,
			`origin-${String(originIndex + 1).padStart(2, "0")}-${spec.minutes}.geojson`,
		);
		await writeFile(path.join(root, filename), json, { flag: "wx" });
		const row = {
			minutes: spec.minutes,
			diagnostic: spec.diagnostic,
			fieldStats: result.fieldStats,
			stats: result.stats,
			timings,
			frame: result.frame,
			maxObservedQueryArrayBuffers,
			afterReleaseArrayBuffers: released.arrayBuffers,
			output: { filename, bytes: Buffer.byteLength(json), sha256: sha(json) },
			hostPhaseMsIncludingQueryChecks: performance.now() - runBegan,
		};
		results.push(row);
		process.stdout.write(
			`${JSON.stringify({ minutes: spec.minutes, step: result.frame.step, cells: result.frame.width * result.frame.height, maxObservedQueryArrayBuffers })}\n`,
		);
	}
	const report = {
		status:
			"highest_saved_queue_pressure_corrected_finer_display_capacity_pilot_complete",
		recipeSha256: pin,
		origins: 1,
		originIndex,
		selection:
			"Highest maximumHeapEntries across every saved coarse display; first index breaks ties",
		displays: results.length,
		diagnosticPointCases: samples.length,
		results,
		heldBackingBytes: held,
		baseline,
		afterLoad,
		afterQueries: await settledPhaseMemory(),
		providerRequests: requests,
		hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC:
			performance.now() - began,
		isAccuracyCandidate: false,
		higherResolutionEvaluated: true,
		scope: plan.scope,
	};
	assert.equal(report.afterQueries.arrayBuffers, afterLoad.arrayBuffers);
	assert.equal(requests, 0);
	await writeFile(
		path.join(root, "report.json"),
		`${JSON.stringify(report, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(
		`${JSON.stringify({ status: report.status, displays: report.displays, hostTotalMs: report.hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC })}\n`,
	);
} catch (error) {
	await settledPhaseMemory();
	const afterFailure = await settledPhaseMemory();
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error), activeMinutes, lastObservedQueryArrayBuffers, immutableSeedingChecked, providerRequests: requests, heldArrayBuffers, afterFailure, observedQueryBuffers: queryBuffers.length, queryBuffersReleased: queryBuffers.length === 0 ? null : queryBuffers.every((b) => b.deref() === undefined), afterFailureMayAlsoCollectRuntimeInputs: true, stack: error instanceof Error ? error.stack : null, hostTotalMs: performance.now() - began }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
