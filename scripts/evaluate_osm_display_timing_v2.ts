/** V2 preserves unsupported source rows and reuses all completed V1 phases. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { writeFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { containsPolygon } from "../src/server/coarse-contours.ts";
import { diagnosticFilledDisplay } from "./coarse_osm_diagnostic_display_v1.ts";
import { computeDiagnosticRoadField } from "./coarse_osm_diagnostic_field_v1.ts";
import { numericalGates } from "./coarse_osm_display_gates_v1.ts";
import {
	displayPointTiming,
	type PointTiming,
} from "./coarse_osm_display_timing_v1.ts";
import { filledDisplay } from "./coarse_osm_filled_display_v1.ts";
import type {
	OriginConnection,
	OriginGeography,
} from "./coarse_osm_origin_connections_v1.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { computeRoadField } from "./coarse_osm_road_field_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { timingRow } from "./coarse_osm_timing_rows_v2.ts";
import type { TimingRow } from "./coarse-damped-gates.ts";

type Place = { lon: number; lat: number };
type Sample = TimingRow & {
	id: string;
	origin: Place;
	destination: Place;
	valhallaMinutes: number | null;
};
type Polygon = Parameters<typeof containsPolygon>[1];
const repo = path.resolve(import.meta.dirname, ".."),
	coordinate = (p: Place): Coordinate => [p.lon, p.lat],
	key = (p: Place) => JSON.stringify(coordinate(p));
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");

function diagnosticPhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	source: OriginConnection,
	samples: Sample[],
	connections: Map<string, OriginConnection | null>,
	root: string,
	filename: string,
	check: () => void,
) {
	const began = performance.now(),
		field = computeDiagnosticRoadField(
			graph,
			geometry,
			source.snap,
			source.connectorTicks,
			{ maxTicks: 432000, check },
		);
	const timings: Record<string, PointTiming> = {};
	const display = diagnosticFilledDisplay(
		graph,
		geometry,
		geography,
		source,
		field,
		{
			check,
			probe: (grid) => {
				for (const sample of samples)
					timings[sample.id] = displayPointTiming(
						graph,
						geometry,
						geography,
						field,
						grid,
						source.origin,
						coordinate(sample.destination),
						connections.get(key(sample.destination)) ?? null,
					);
			},
		},
	);
	const json = JSON.stringify(display.output);
	writeFileSync(path.join(root, filename), json, { flag: "wx" });
	assert.equal(Object.keys(timings).length, samples.length);
	return {
		timings,
		frame: display.frame,
		stats: display.stats,
		phaseMs: performance.now() - began,
		output: {
			filename,
			bytes: Buffer.byteLength(json),
			sha256: sha(Buffer.from(json)),
		},
	};
}
function productionPhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	source: OriginConnection,
	samples: Sample[],
	minutes: number,
	root: string,
	filename: string,
	check: () => void,
) {
	const field = computeRoadField(
		graph,
		geometry,
		source.snap,
		source.connectorTicks,
		{ maxTicks: minutes * 480, check },
	);
	const display = filledDisplay(graph, geometry, geography, source, field, {
		check,
	});
	const classified = Object.fromEntries(
		samples.map((sample) => [
			sample.id,
			display.output.coordinates.some((poly) =>
				containsPolygon([sample.destination.lon, sample.destination.lat], poly),
			),
		]),
	);
	const json = JSON.stringify(display.output);
	writeFileSync(path.join(root, filename), json, { flag: "wx" });
	return {
		classified,
		frame: display.frame,
		stats: display.stats,
		output: {
			filename,
			bytes: Buffer.byteLength(json),
			sha256: sha(Buffer.from(json)),
		},
	};
}

async function main() {
	const began = performance.now(),
		[recipeName, pin] = process.argv.slice(2);
	assert.ok(recipeName && pin && global.gc);
	const raw = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(raw), pin);
	const plan = JSON.parse(raw.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-car-display-timing-evaluation-v2",
	);
	assert.equal(plan.controlsPassed, 2);
	assert.equal(plan.hostSeconds, 1200);
	assert.equal(plan.maxOwnedBytes, 134217728);
	assert.ok(
		plan.priorReserveBytes +
			plan.newClosedAllocationBytes +
			plan.metadataScratchReserveBytes +
			plan.maxOwnedBytes <
			64 * 1024 ** 3,
	);
	for (const [name, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), raw, { flag: "wx" });
	let outboundCalls = 0;
	globalThis.fetch = async () => {
		outboundCalls++;
		throw new Error("Unexpected outbound request");
	};
	const check = () => {
		assert.ok(
			performance.now() - began < plan.hostSeconds * 1000,
			"Timing host deadline",
		);
		assert.ok(
			process.memoryUsage().rss < 4 * 1024 ** 3,
			"Timing host RSS bound",
		);
	};
	try {
		const saved = JSON.parse(
			(await readFile(path.join(repo, plan.baseline))).toString("utf8"),
		);
		const samples: Sample[] = saved.rows;
		assert.equal(samples.length, 83);
		assert.equal(samples.filter((s) => s.valhallaMinutes !== null).length, 35);
		const referenceKeys = samples.map((s) => s.id);
		assert.equal(new Set(referenceKeys).size, 83);
		const originalOutputs = JSON.parse(
			(await readFile(path.join(repo, plan.savedDisplayReport))).toString(
				"utf8",
			),
		);
		const previousPlan = JSON.parse(
			(await readFile(path.join(repo, plan.savedDisplayPlan))).toString("utf8"),
		);
		const baselineMemory = await settledPhaseMemory();
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
		const geo = await loadOriginGeography(
			path.join(repo, plan.geographySource),
			plan.geographyManifestSha256,
		);
		const accessRows = JSON.parse(
			(await readFile(path.join(repo, plan.savedConnections))).toString("utf8"),
		) as {
			coordinate: Coordinate;
			connection: OriginConnection | null;
			reason: string | null;
		}[];
		assert.equal(accessRows.length, 79);
		const connections = new Map(
			accessRows.map((row) => [JSON.stringify(row.coordinate), row.connection]),
		);
		for (const place of samples.flatMap((s) => [s.origin, s.destination]))
			assert.ok(connections.has(key(place)));
		const completed = new Map();
		for (const name of plan.completedRecords as string[]) {
			const record = JSON.parse(
				(await readFile(path.join(repo, name))).toString("utf8"),
			);
			completed.set(JSON.stringify(record.origin), {
				...record,
				recordPath: name,
			});
		}
		assert.equal(completed.size, 18);
		const afterLoad = await settledPhaseMemory();
		await writeFile(
			path.join(root, "connections.json"),
			`${JSON.stringify(accessRows, null, 2)}\n`,
			{ flag: "wx" },
		);

		const origins = new Map(samples.map((s) => [key(s.origin), s.origin])),
			rows: Sample[] = [],
			phases = [];
		let index = 0,
			reused = 0,
			produced = 0,
			reusedDiagnosticPhases = 0,
			reusedV1ProductionDisplays = 0,
			newDiagnosticPhases = 0,
			unsupportedSourceCases = 0;
		for (const [originKey, origin] of origins) {
			const source = connections.get(originKey);

			const selected = samples.filter((s) => key(s.origin) === originKey),
				stem = `origin-${String(++index).padStart(2, "0")}`;
			if (!source) {
				const failure = accessRows.find(
					(row) => JSON.stringify(row.coordinate) === originKey,
				)?.reason;
				assert.ok(failure);
				for (const sample of selected)
					rows.push(timingRow(sample, null, false, failure));
				unsupportedSourceCases += selected.length;
				const phase = {
					origin: coordinate(origin),
					sourceConnectionFailure: failure,
					cases: selected.map((s) => s.id),
					estimateProduced: false,
				};
				phases.push(phase);
				await writeFile(
					path.join(root, `${stem}.json`),
					`${JSON.stringify(phase, null, 2)}\n`,
					{ flag: "wx" },
				);
				process.stdout.write(
					`${JSON.stringify({ origin: index, origins: origins.size, cases: selected.length, unsupportedSource: failure })}\n`,
				);
				continue;
			}
			const priorPhase = completed.get(originKey);
			let diagnostic: ReturnType<typeof diagnosticPhase>;
			if (priorPhase) {
				diagnostic = priorPhase.diagnostic;
				reusedDiagnosticPhases++;
			} else {
				diagnostic = diagnosticPhase(
					core.graph,
					paid.geometry,
					geo.geography,
					source,
					selected,
					connections,
					root,
					`${stem}-900.geojson`,
					check,
				);
				newDiagnosticPhases++;
			}

			const afterDiagnosticRelease = await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after diagnostic field/display summary",
			);
			const classified: Record<string, boolean> = {},
				productions = [];
			for (const budget of new Set(selected.map((s) => s.budgetMinutes))) {
				const subset = selected.filter((s) => s.budgetMinutes === budget);
				const existing = priorPhase?.productions.find(
					(value: { budget: number; classified?: Record<string, boolean> }) =>
						value.budget === budget && value.classified,
				);
				if (existing) {
					Object.assign(classified, existing.classified);
					productions.push({
						...existing,
						reusedFromV1Record: priorPhase.recordPath,
					});
					reusedV1ProductionDisplays++;
					continue;
				}
				const priorSource = previousPlan.sources.find(
					(s: { coordinate: Coordinate }) =>
						JSON.stringify(s.coordinate) === originKey,
				);
				const prior = priorSource
					? originalOutputs.rows.find(
							(row: { sourceId: string; minutes: number }) =>
								row.sourceId === priorSource.id && row.minutes === budget,
						)
					: null;
				if (prior) {
					const output = await readFile(
						path.join(repo, previousPlan.output, prior.output.filename),
					);
					assert.equal(sha(output), prior.output.sha256);
					assert.equal(output.length, prior.output.bytes);
					const polygons = JSON.parse(output.toString("utf8"))
						.coordinates as Polygon[];
					for (const sample of subset)
						classified[sample.id] = polygons.some((poly) =>
							containsPolygon(
								[sample.destination.lon, sample.destination.lat],
								poly,
							),
						);
					productions.push({
						budget,
						reusedQualifiedOutput: true,
						output: prior.output,
					});
					reused++;
				} else {
					const display = productionPhase(
						core.graph,
						paid.geometry,
						geo.geography,
						source,
						subset,
						budget,
						root,
						`${stem}-${budget}.geojson`,
						check,
					);
					Object.assign(classified, display.classified);
					productions.push({
						budget,
						reusedQualifiedOutput: false,
						...display,
					});
					produced++;
				}
				await assertPhaseReleased(
					afterLoad.arrayBuffers,
					"after production display/reused output",
				);
			}
			for (const sample of selected) {
				const shaded = classified[sample.id];
				assert.equal(typeof shaded, "boolean");
				rows.push(
					timingRow(sample, diagnostic.timings[sample.id].ticks, shaded),
				);
			}

			const phase = {
				origin: coordinate(origin),
				diagnostic,
				productions,
				afterDiagnosticRelease,
				reusedV1Record: priorPhase?.recordPath ?? null,
			};
			phases.push(phase);
			await writeFile(
				path.join(root, `${stem}.json`),
				`${JSON.stringify(phase, null, 2)}\n`,
				{ flag: "wx" },
			);
			process.stdout.write(
				`${JSON.stringify({ origin: index, origins: origins.size, cases: selected.length, finite: selected.filter((s) => diagnostic.timings[s.id].ticks !== null).length, diagnosticMs: diagnostic.phaseMs })}\n`,
			);
		}
		assert.equal(rows.length, 83);
		assert.deepEqual(
			[...rows.map((r) => r.id)].sort(),
			[...referenceKeys].sort(),
		);
		assert.equal(outboundCalls, 0);
		const report = {
			status: "completed_fixed_numerical_and_shading_screen",
			recipeSha256: pin,
			...numericalGates(rows),
			rows,
			phases,
			originalCases: 83,
			valhallaCases: 35,
			origins: origins.size,
			reusedProductionDisplays: reused,
			newProductionDisplays: produced,
			reusedDiagnosticPhases,
			reusedV1ProductionDisplays,
			newDiagnosticPhases,
			unsupportedSourceCases,
			providerRequests: outboundCalls,
			baselineMemory,
			afterLoad,
			afterQueries: await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after all timing/display phases",
			),
			hostTotalMs: performance.now() - began,
			candidateAdmitted: false,
			pending: [
				"All166 complete independently reconciled road/local path sums",
				"Full physical/source/shore/transfer checks",
				"Whole app/package/retained/API/shared-camera gates",
			],
			scope:
				"All83 saved ORS /35 Valhalla observed development cases against unchanged v9. Point times use fixed900-minute diagnostic road/local finish; actual original-budget filled outputs determine shading. V1 source-assertion stop preserved; all18 completed diagnostics/10 production outputs reused without rerouting. Unsupported source cases retained as explicit failed/null/unshaded rows. Nulls/classification failures retained. Numerical screen only: local suffix sums are checked, complete road path witnesses pending and never counted as passed. No provider/DB/env/source-download/deployment operation. Host RSS/deadline software guard, not protected cgroup/CPU/swap or cloud timing.",
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, numericalGatesPassed: report.numericalGatesPassed, gates: report.gates, overall: report.overall, hostTotalMs: report.hostTotalMs })}\n`,
		);
	} catch (error) {
		await writeFile(
			path.join(root, "failure.json"),
			`${JSON.stringify({ error: String(error), stack: error instanceof Error ? error.stack : null, hostMs: performance.now() - began }, null, 2)}\n`,
			{ flag: "wx" },
		);
		throw error;
	}
}
await main();
