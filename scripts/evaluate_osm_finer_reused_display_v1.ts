/** One finer-grid candidate using qualified private query-buffer reuse. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { containsPolygon } from "../src/server/coarse-contours.ts";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import type { PointTiming } from "./coarse_osm_access_timing_v2.ts";
import {
	finishAccessPointTiming,
	type PreparedPointTiming,
	prepareAccessPointTiming,
} from "./coarse_osm_access_timing_v3.ts";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import { numericalGates } from "./coarse_osm_display_gates_v1.ts";
import { bit, cellAt, center } from "./coarse_osm_display_grid_v3.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import { settledPhaseMemory } from "./coarse_osm_phase_lifetime_v1.ts";
import { reusedContextDisplay } from "./coarse_osm_reused_display_v2.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV6 } from "./coarse_osm_routing_geography_v6.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { timingRow } from "./coarse_osm_timing_rows_v2.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";
import type { TimingRow } from "./coarse-damped-gates.ts";

type Sample = TimingRow & {
	id: string;
	origin: { lon: number; lat: number };
	destination: { lon: number; lat: number };
	valhallaMinutes: number | null;
};
type PublicPointObservation = {
	id: string;
	originIndex: number;
	minutes: number;
	pointOnMask: boolean;
	cell: number;
	cellCenter: Coordinate | null;
	centerOnMask: boolean | null;
	cellCovered: boolean;
	localSeconds: number | null;
	roadFootConnectionAllowed: boolean | null;
	shaded: boolean;
};
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
assert.equal(plan.output, "data/coarse-quality/us-osm-finer-reused-display-v1");
assert.deepEqual(
	plan.originIndices,
	Array.from({ length: 21 }, (_, i) => i),
);
assert.equal(plan.hostSeconds, 10800);
assert.equal(plan.maxOwnedBytes, 268435456);
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
	assert.ok(performance.now() - began < 10800000, "Finer display deadline");
	assert.ok(process.memoryUsage().rss < 4 * 1024 ** 3, "Finer display RSS");
};
try {
	const parity = await loadJson(plan.parityReport);
	assert.equal(
		parity.status,
		"all_saved_origins_reused_display_same_resolution_parity_complete",
	);
	assert.equal(parity.displays, 58);
	assert.equal(parity.diagnosticPointCases, 83);
	const candidate = await loadJson(plan.candidate);
	assert.equal(candidate.phases.length, 21);
	const baselineSamples = (await loadJson(plan.baseline)).rows as Sample[];
	assert.equal(baselineSamples.length, 83);
	assert.equal(
		baselineSamples.filter((s) => s.valhallaMinutes !== null).length,
		35,
	);
	assert.deepEqual(
		baselineSamples.map((s) => s.id).sort(),
		candidate.rows.map((s: Sample) => s.id).sort(),
	);
	const records = (await loadJson(plan.connections)) as {
		coordinate: Coordinate;
		connection: OriginConnection | null;
	}[];
	const connections = new Map(
		records.map((row) => [key(row.coordinate), row.connection]),
	);
	const access = await loadJson(plan.accessReport);
	const inputs = candidate.phases.map((phase: { origin: Coordinate }) => {
		const source = connections.get(key(phase.origin));
		assert.ok(source);
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
		return { source, starts: accessStarts(source, choices) };
	});
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
	const held = afterLoad.arrayBuffers - baseline.arrayBuffers;
	assert.ok(held <= 162238546);
	const results = [];
	const phases = [];
	const rows: Sample[] = [];
	const productionPointObservations: PublicPointObservation[] = [];
	let diagnosticPointCases = 0;
	for (const [originIndex, phase] of candidate.phases.entries()) {
		const { source, starts } = inputs[originIndex];
		const samples = baselineSamples.filter(
			(row: { origin: { lon: number; lat: number } }) =>
				key(xy(row.origin)) === key(phase.origin),
		);
		diagnosticPointCases += samples.length;
		const displays = [];
		const classified: Record<string, boolean> = {};
		let diagnosticTimings: Record<string, PointTiming> = {};
		const specs = [
			{ minutes: 900, expected: phase.diagnostic, diagnostic: true },
			...phase.productions.map((p: { minutes: number }) => ({
				minutes: p.minutes,
				expected: p,
				diagnostic: false,
			})),
		];

		for (const spec of specs) {
			check();
			const publicPoints: Omit<PublicPointObservation, "shaded">[] = [];
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
							sha(new Uint8Array(field.seeds.buffer)),
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
						const extra =
							process.memoryUsage().arrayBuffers - afterLoad.arrayBuffers;
						maxObservedQueryArrayBuffers = Math.max(
							maxObservedQueryArrayBuffers,
							extra,
						);
						assert.ok(extra <= 67108864, "Observed query backing cap");
						if (observations++ === 0)
							assert.deepEqual(
								[buffers[0], buffers[1], buffers[5]].map((b) =>
									sha(new Uint8Array(b)),
								),
								fingerprints,
								"Road seeding changed query labels",
							);
					},
					probe: (grid) => {
						if (spec.diagnostic)
							for (let i = 0; i < samples.length; i++)
								timings[samples[i].id] = finishAccessPointTiming(
									geography,
									grid,
									prepared[i],
								);
						else
							for (const sample of samples.filter(
								(s) => s.budgetMinutes === spec.minutes,
							)) {
								const target = xy(sample.destination);
								const connection = connections.get(key(target));
								const cell = cellAt(grid.frame, target);
								publicPoints.push({
									id: sample.id,
									originIndex,
									minutes: spec.minutes,
									pointOnMask: landConnection(
										geography,
										[...target],
										[...target],
									),
									cell,
									cellCenter: cell < 0 ? null : center(grid.frame, cell),
									centerOnMask: cell < 0 ? null : Boolean(bit(grid.land, cell)),
									cellCovered: cell >= 0 && Boolean(bit(grid.coverage, cell)),
									localSeconds:
										cell < 0 || grid.times[cell] === 65535
											? null
											: grid.times[cell],
									roadFootConnectionAllowed: connection
										? landConnection(
												geography,
												[...target],
												[...connection.snap.coordinate],
											)
										: null,
								});
							}
					},
				},
				spec.diagnostic,
			);
			assert.equal(observations, 2);
			assert.deepEqual(
				result.fieldStats,
				spec.expected.fieldStats,
				"Same source road query",
			);
			assert.ok(
				result.frame.step <= spec.expected.frame.step,
				"Finer capacity cannot coarsen these old frames",
			);
			assert.ok(result.stats.maximumBackingBufferBytes <= 67108864);
			assert.ok(
				maxObservedQueryArrayBuffers <= result.stats.maximumBackingBufferBytes,
			);
			if (spec.diagnostic) {
				for (const sample of samples)
					assert.equal(
						timings[sample.id].roadTicks,
						spec.expected.timings[sample.id].roadTicks,
						"Unchanged road-only point ticks",
					);
				diagnosticTimings = timings;
			} else {
				for (const sample of samples.filter(
					(s) => s.budgetMinutes === spec.minutes,
				))
					classified[sample.id] = result.output.coordinates.some((poly) =>
						containsPolygon([...xy(sample.destination)], poly),
					);
				for (const observation of publicPoints)
					productionPointObservations.push({
						...observation,
						shaded: classified[observation.id],
					});
			}
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
				originIndex,
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
			displays.push(row);
			process.stdout.write(
				`${JSON.stringify({ originIndex, minutes: spec.minutes, oldStep: spec.expected.frame.step, step: result.frame.step, cells: result.frame.width * result.frame.height, maxObservedQueryArrayBuffers })}\n`,
			);
		}
		for (const sample of samples) {
			assert.equal(typeof classified[sample.id], "boolean");
			rows.push(
				timingRow(
					sample,
					diagnosticTimings[sample.id].ticks,
					classified[sample.id],
				),
			);
		}
		phases.push({
			origin: phase.origin,
			initialChoices: starts.length,
			accessInput: phase.accessInput,
			diagnostic: displays[0],
			productions: displays.slice(1),
		});
	}
	assert.equal(rows.length, 83);
	assert.deepEqual(
		rows.map((s) => s.id).sort(),
		baselineSamples.map((s) => s.id).sort(),
	);
	assert.equal(results.length, 58);
	assert.equal(diagnosticPointCases, 83);
	assert.equal(productionPointObservations.length, 83);
	assert.deepEqual(
		productionPointObservations.map((p) => p.id).sort(),
		baselineSamples.map((s) => s.id).sort(),
	);
	const report = {
		status: "all58_finer_reused_display_candidate_complete",
		recipeSha256: pin,
		candidateModel:
			"osm-car-tagged-static90-inactive-conditional-finer-display-v1",
		...numericalGates(rows),
		rows,
		phases,
		productionPointObservations,
		originalCases: 83,
		diagnosticDisplays: 21,
		productionDisplays: 37,
		valhallaCases: 35,
		frozenLocalGridOrMapsReused: false,
		endpointCollectionsRecomputed: false,
		endpointCollectionsReusedByIdentity: true,
		retainedBackingBytes: held,
		retainedBackingGatePassed: held <= 162238546,
		candidateAdmitted: false,
		pending: [
			"All166 source/shore/transfer/path witnesses with bounded root replay",
			"Full app/package/retained/first-estimate/API/shared-camera gates",
		],
		origins: candidate.phases.length,
		displays: results.length,
		diagnosticPointCases,
		results,
		heldBackingBytes: held,
		baseline,
		afterLoad,
		afterQueries: await settledPhaseMemory(),
		providerRequests: requests,
		hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC:
			performance.now() - began,
		isAccuracyCandidate: true,
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
		`${JSON.stringify({ status: report.status, displays: report.displays, overall: report.overall, gates: report.gates, hostTotalMs: report.hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC })}\n`,
	);
} catch (error) {
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error), stack: error instanceof Error ? error.stack : null, hostTotalMs: performance.now() - began }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
