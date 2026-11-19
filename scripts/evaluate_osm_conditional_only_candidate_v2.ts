/** Compare the mandatory-turn graph using the established renderer and references. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { containsPolygon } from "../src/server/coarse-contours.ts";
import {
	accessFilledDisplay,
	diagnosticAccessFilledDisplay,
} from "./coarse_osm_access_display_v3.ts";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import type {
	AccessRoadField,
	AccessStart,
} from "./coarse_osm_access_road_field_v2.ts";
import {
	accessDisplayPointTiming,
	type PointTiming,
} from "./coarse_osm_access_timing_v2.ts";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import {
	withAccessContextRoadField,
	withDiagnosticContextRoadField,
} from "./coarse_osm_context_road_field_v1.ts";
import { numericalGates } from "./coarse_osm_display_gates_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v2.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV6 as waterRoutingGeography } from "./coarse_osm_routing_geography_v6.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { timingRow } from "./coarse_osm_timing_rows_v2.ts";
import type { TurnContexts } from "./coarse_osm_turn_contexts_v1.ts";
import { waterCellFlags } from "./coarse_osm_water_lookup_v1.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";
import type { TimingRow } from "./coarse-damped-gates.ts";
import { timingSummary } from "./coarse-damped-gates.ts";

type Place = { lon: number; lat: number };
type Sample = TimingRow & {
	id: string;
	origin: Place;
	destination: Place;
	valhallaMinutes: number | null;
};
const repo = path.resolve(import.meta.dirname, ".."),
	coordinate = (p: Place): Coordinate => [p.lon, p.lat],
	key = (p: Place) => JSON.stringify(coordinate(p));
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");

function diagnosticPhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	contexts: TurnContexts,
	geography: OriginGeography,
	source: OriginConnection,
	starts: AccessStart[],
	samples: Sample[],
	connections: Map<string, OriginConnection | null>,
	root: string,
	filename: string,
	check: () => void,
) {
	const began = performance.now();
	return withDiagnosticContextRoadField(
		graph,
		geometry,
		contexts,
		starts,
		(field) => {
			const fingerprints = fieldFingerprints(field);
			const timings: Record<string, PointTiming> = {};
			const display = diagnosticAccessFilledDisplay(
				graph,
				geometry,
				geography,
				source,
				field,
				{
					check,
					probe: (grid) => {
						for (const sample of samples)
							timings[sample.id] = accessDisplayPointTiming(
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
			assert.deepEqual(fieldFingerprints(field), fingerprints);
			const json = JSON.stringify(display.output);
			writeFileSync(path.join(root, filename), json, { flag: "wx" });
			assert.equal(Object.keys(timings).length, samples.length);
			return {
				timings,
				fieldStats: field.stats,
				restorationChecked: true,
				frame: display.frame,
				stats: display.stats,
				phaseMs: performance.now() - began,
				output: {
					filename,
					bytes: Buffer.byteLength(json),
					sha256: sha(Buffer.from(json)),
				},
			};
		},
		{ maxTicks: 432000, check },
	);
}
function productionPhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	contexts: TurnContexts,
	geography: OriginGeography,
	source: OriginConnection,
	starts: AccessStart[],
	samples: Sample[],
	minutes: number,
	root: string,
	filename: string,
	check: () => void,
) {
	return withAccessContextRoadField(
		graph,
		geometry,
		contexts,
		starts,
		(field) => {
			const fingerprints = fieldFingerprints(field);
			const display = accessFilledDisplay(
				graph,
				geometry,
				geography,
				source,
				field,
				{
					check,
				},
			);
			const classified = Object.fromEntries(
				samples.map((sample) => [
					sample.id,
					display.output.coordinates.some((poly) =>
						containsPolygon(
							[sample.destination.lon, sample.destination.lat],
							poly,
						),
					),
				]),
			);
			assert.deepEqual(fieldFingerprints(field), fingerprints);
			const json = JSON.stringify(display.output);
			writeFileSync(path.join(root, filename), json, { flag: "wx" });
			return {
				classified,
				fieldStats: field.stats,
				restorationChecked: true,
				frame: display.frame,
				stats: display.stats,
				output: {
					filename,
					bytes: Buffer.byteLength(json),
					sha256: sha(Buffer.from(json)),
				},
			};
		},
		{ maxTicks: minutes * 480, check },
	);
}

function fieldFingerprints(field: AccessRoadField) {
	return [
		sha(new Uint8Array(field.labels.buffer)),
		sha(new Uint8Array(field.vertexArrivalSeconds.buffer)),
		sha(new Uint8Array(field.seeds.buffer)),
	];
}
function choicesFor(
	root: string,
	output: {
		filename: string;
		sha256: string;
		rawSha256: string;
		compressedBytes: number;
		rawBytes: number;
	},
) {
	assert.match(output.filename, /^endpoint-\d{2}\.json\.gz$/);
	assert.ok(output.rawBytes <= 4194304);
	const compressed = readFileSync(path.join(root, output.filename));
	assert.equal(compressed.length, output.compressedBytes);
	assert.equal(sha(compressed), output.sha256);
	const raw = gunzipSync(compressed, { maxOutputLength: 4194304 });
	assert.equal(raw.length, output.rawBytes);
	assert.equal(sha(raw), output.rawSha256);
	return JSON.parse(raw.toString("utf8")) as OriginConnection[];
}
type CompletedPhase = {
	origin: Coordinate;
	initialChoices: number;
	accessInput: Parameters<typeof choicesFor>[1];
	diagnostic: ReturnType<typeof diagnosticPhase>;
	productions: ({ minutes: number } & ReturnType<typeof productionPhase>)[];
};

async function restoreCompletedPhase(
	checkpoint: {
		root: string;
		roster: Record<string, { bytes: number; sha256: string }>;
	},
	root: string,
	stem: string,
	origin: Coordinate,
	samples: Sample[],
	choices: number,
	accessInput: CompletedPhase["accessInput"],
): Promise<CompletedPhase> {
	async function readBound(name: string) {
		const asset = checkpoint.roster[name];
		assert.ok(asset && asset.bytes <= 3_000_000);
		const raw = await readFile(path.join(repo, checkpoint.root, name));
		assert.equal(raw.length, asset.bytes);
		assert.equal(sha(raw), asset.sha256, name);
		return raw;
	}
	const name = `${stem}.json`;
	const phase = JSON.parse(
		(await readBound(name)).toString("utf8"),
	) as CompletedPhase;
	assert.deepEqual(phase.origin, origin);
	assert.equal(phase.initialChoices, choices);
	assert.deepEqual(phase.accessInput, accessInput);
	assert.equal(phase.diagnostic.restorationChecked, true);
	assert.deepEqual(
		Object.keys(phase.diagnostic.timings).sort(),
		samples.map((s) => s.id).sort(),
	);
	assert.deepEqual(
		phase.productions.map((p) => p.minutes),
		[...new Set(samples.map((s) => s.budgetMinutes))],
	);
	for (const { minutes, output, classified } of phase.productions) {
		assert.equal(output.filename, `${stem}-${minutes}.geojson`);
		assert.deepEqual(
			Object.keys(classified).sort(),
			samples
				.filter((s) => s.budgetMinutes === minutes)
				.map((s) => s.id)
				.sort(),
		);
		assert.ok(Object.values(classified).every((v) => typeof v === "boolean"));
	}
	assert.equal(phase.diagnostic.output.filename, `${stem}-900.geojson`);
	for (const { output } of [phase.diagnostic, ...phase.productions]) {
		const raw = await readBound(output.filename);
		assert.equal(raw.length, output.bytes);
		assert.equal(sha(raw), output.sha256);
		await writeFile(path.join(root, output.filename), raw, { flag: "wx" });
	}
	return phase;
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
		"data/coarse-quality/us-osm-conditional-only-evaluation-v2",
	);
	assert.equal(plan.controlsPassed, 45);
	assert.equal(plan.hostSeconds, 3600);
	assert.equal(plan.maxOwnedBytes, 268435456);
	assert.ok(
		plan.priorReserveBytes +
			plan.newClosedAllocationBytes +
			plan.metadataScratchReserveBytes +
			plan.maxOwnedBytes <
			72 * 1024 ** 3,
	);
	for (const [name, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
	const checkpoint = JSON.parse(
		(await readFile(path.join(repo, plan.checkpoint))).toString("utf8"),
	);
	assert.equal(
		checkpoint.root,
		"data/coarse-quality/us-osm-conditional-only-evaluation-v1",
	);
	assert.equal(checkpoint.terminalRecord, "failure.json");
	const priorPlan = JSON.parse(
		(await readFile(path.join(repo, plan.priorRecipe))).toString("utf8"),
	);
	for (const [name, value] of Object.entries(priorPlan)) {
		if (
			[
				"bindings",
				"newClosedAllocationBytes",
				"previousClosedRoots",
				"output",
				"scope",
			].includes(name)
		)
			continue;
		assert.deepEqual(plan[name], value, name);
	}
	for (const [name, digest] of Object.entries(priorPlan.bindings))
		assert.equal(plan.bindings[name], digest, name);
	const restoredOrigins = new Set<string>(plan.restoredOrigins);
	assert.deepEqual(
		[...restoredOrigins],
		["origin-01", "origin-02", "origin-03"],
	);
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
			performance.now() - began < 3600000,
			"Access candidate host deadline",
		);
		assert.ok(
			process.memoryUsage().rss < 4 * 1024 ** 3,
			"Access candidate host RSS bound",
		);
	};
	try {
		const baseline = JSON.parse(
				(await readFile(path.join(repo, plan.baseline))).toString("utf8"),
			),
			samples = baseline.rows as Sample[];
		assert.equal(samples.length, 83);
		assert.equal(samples.filter((s) => s.valhallaMinutes !== null).length, 35);
		const accessRows = JSON.parse(
			(await readFile(path.join(repo, plan.originalConnections))).toString(
				"utf8",
			),
		) as {
			coordinate: Coordinate;
			connection: OriginConnection | null;
			reason: string | null;
		}[];
		const connections = new Map(
			accessRows.map((row) => [JSON.stringify(row.coordinate), row.connection]),
		);
		assert.equal(connections.size, 79);
		const access = JSON.parse(
			(await readFile(path.join(repo, plan.accessReport))).toString("utf8"),
		);
		assert.equal(access.inputs, 79);
		assert.ok(access.supported >= 78 && access.supported <= 79);
		assert.equal(access.originalSupportedInputsRetained, 78);
		const accessByCoordinate = new Map<
			string,
			{ supported: boolean; output: Parameters<typeof choicesFor>[1] }
		>(
			access.rows.map((row: { coordinate: Coordinate }) => [
				JSON.stringify(row.coordinate),
				row,
			]),
		);
		const priorAccess = JSON.parse(
			await readFile(path.join(repo, plan.previousAccessReport), "utf8"),
		);
		assert.equal(priorAccess.rows.length, 79);
		for (let i = 0; i < access.rows.length; i++) {
			assert.deepEqual(
				access.rows[i].coordinate,
				priorAccess.rows[i].coordinate,
			);
			// Recovered roads can change attachments and their numeric source IDs.
		}
		const previous = JSON.parse(
			(await readFile(path.join(repo, plan.previousCandidate))).toString(
				"utf8",
			),
		);
		const oldRoadTicks = new Map<string, number | null>();
		for (const phase of previous.phases)
			for (const [id, timing] of Object.entries(phase.diagnostic.timings) as [
				string,
				PointTiming,
			][]) {
				assert.ok(!oldRoadTicks.has(id));
				oldRoadTicks.set(id, timing.roadTicks);
			}
		assert.equal(oldRoadTicks.size, 83);
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
		const history = await loadTurnContexts(
			path.join(repo, plan.contextSource),
			plan.contextManifestSha256,
			path.join(repo, plan.coreSource),
			plan.coreManifestSha256,
			core.graph,
			check,
		);
		assert.equal(history.contexts.states, plan.contextStates);
		assert.equal(
			history.retainedDataBackingBufferBytes,
			plan.contextDataBackingBytes,
		);
		const coarse = await loadOriginGeography(
			path.join(repo, plan.geographySource),
			plan.geographyManifestSha256,
		);
		const packet = await loadWaterRasterV2(
			path.join(repo, plan.waterSource),
			plan.waterManifestSha256,
		);
		const geography = waterRoutingGeography(coarse.geography, packet);
		const observedPacket = JSON.parse(
			await readFile(path.join(repo, plan.readerObservations), "utf8"),
		);
		for (const row of observedPacket.observations) {
			const expected =
				row.kind === "outside-grid"
					? null
					: (row.waterAtCenter ? 1 : 0) | (row.sourceUncertainty ? 2 : 0);
			assert.equal(waterCellFlags(packet, row.coordinate), expected);
		}
		assert.equal(observedPacket.observations.length, 1002);
		const accessAuditStarted = performance.now();
		let validatedInitialChoices = 0;
		for (const row of access.rows) {
			check();
			const onMask = landConnection(geography, row.coordinate, row.coordinate);
			assert.ok(onMask && row.supported && !row.offMask);
			for (const choice of choicesFor(
				path.join(repo, plan.accessSource),
				row.output,
			)) {
				const price = connectorPrice(choice.origin, choice.snap.coordinate);
				assert.equal(price.ticks, choice.connectorTicks);
				assert.equal(price.meters, choice.connectorMeters);
				if (choice.snap.distanceMeters > 1)
					assert.ok(
						landConnection(
							geography,
							[...choice.origin],
							[...choice.snap.coordinate],
						),
					);
				validatedInitialChoices++;
			}
		}
		assert.equal(validatedInitialChoices, access.totalConnections);
		const accessAuditMs = performance.now() - accessAuditStarted;
		process.stdout.write(
			`${JSON.stringify({ validatedInitialChoices, accessAuditMs })}\n`,
		);
		const roadArrivalTimeIncreases: {
			id: string;
			previous: number;
			current: number | null;
		}[] = [];
		const afterLoad = await settledPhaseMemory(),
			origins = new Map(samples.map((s) => [key(s.origin), s.origin])),
			rows: Sample[] = [],
			phases = [];
		let index = 0,
			productionDisplays = 0,
			diagnosticDisplays = 0,
			unsupportedSourceCases = 0,
			roadArrivalsCompared = 0;
		for (const [originKey, origin] of origins) {
			check();
			const source = connections.get(originKey),
				selected = samples.filter((s) => key(s.origin) === originKey),
				stem = `origin-${String(++index).padStart(2, "0")}`;
			const record = accessByCoordinate.get(originKey);
			assert.ok(record);
			assert.equal(record.supported, source !== null);
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
				continue;
			}
			const alternatives = choicesFor(
					path.join(repo, plan.accessSource),
					record.output,
				),
				starts = accessStarts(source, alternatives);
			const resumed = restoredOrigins.has(stem)
				? await restoreCompletedPhase(
						checkpoint,
						root,
						stem,
						coordinate(origin),
						selected,
						starts.length,
						record.output,
					)
				: null;
			const diagnostic =
				resumed?.diagnostic ??
				diagnosticPhase(
					core.graph,
					paid.geometry,
					history.contexts,
					geography,
					source,
					starts,
					selected,
					connections,
					root,
					`${stem}-900.geojson`,
					check,
				);
			diagnosticDisplays++;
			const afterDiagnosticRelease = await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after multi-source diagnostic summary",
			);
			for (const sample of selected) {
				const old = oldRoadTicks.get(sample.id),
					now = diagnostic.timings[sample.id].roadTicks;
				if (old !== null && old !== undefined) {
					if (now === null || now > old)
						roadArrivalTimeIncreases.push({
							id: sample.id,
							previous: old,
							current: now,
						});
					roadArrivalsCompared++;
				}
			}
			const classified: Record<string, boolean> = {},
				productions = [];
			for (const minutes of new Set(selected.map((s) => s.budgetMinutes))) {
				const subset = selected.filter((s) => s.budgetMinutes === minutes),
					display =
						resumed?.productions.find((p) => p.minutes === minutes) ??
						productionPhase(
							core.graph,
							paid.geometry,
							history.contexts,
							geography,
							source,
							starts,
							subset,
							minutes,
							root,
							`${stem}-${minutes}.geojson`,
							check,
						);
				Object.assign(classified, display.classified);
				productionDisplays++;
				productions.push({ ...display, minutes });
				await assertPhaseReleased(
					afterLoad.arrayBuffers,
					"after multi-source production display summary",
				);
			}
			for (const sample of selected) {
				assert.equal(typeof classified[sample.id], "boolean");
				rows.push(
					timingRow(
						sample,
						diagnostic.timings[sample.id].ticks,
						classified[sample.id],
					),
				);
			}
			const phase = {
				origin: coordinate(origin),
				initialChoices: starts.length,
				accessInput: record.output,
				diagnostic,
				productions,
				afterDiagnosticRelease,
			};

			phases.push(phase);
			await writeFile(
				path.join(root, `${stem}.json`),
				`${JSON.stringify(phase, null, 2)}\n`,
				{ flag: "wx" },
			);
			process.stdout.write(
				`${JSON.stringify({ origin: index, origins: origins.size, choices: starts.length, cases: selected.length, finite: selected.filter((s) => diagnostic.timings[s.id].ticks !== null).length, diagnosticMs: diagnostic.phaseMs })}\n`,
			);
		}
		assert.equal(rows.length, 83);
		assert.deepEqual(
			rows.map((r) => r.id).sort(),
			samples.map((s) => s.id).sort(),
		);
		assert.equal(outboundCalls, 0);
		const common = rows.filter((row) => row.candidate.pointMinutes !== null),
			report = {
				status: "completed_mandatory_turn_full_candidate_screen",
				recipeSha256: pin,
				candidateModel: "osm-car-tagged-static90-conditional-only-v1",
				...numericalGates(rows),
				rows,
				phases,
				commonFiniteComparison: {
					cases: common.length,
					baseline: timingSummary(common, "baseline"),
					candidate: timingSummary(common, "candidate"),
				},
				originalCases: 83,
				valhallaCases: 35,
				origins: 21,
				productionDisplays,
				diagnosticDisplays,
				unsupportedSourceCases,
				roadArrivalsCompared,
				roadArrivalTimeIncreases,
				validatedInitialChoices,
				waterPacketObservationsCompared: observedPacket.observations.length,
				accessAuditMs,
				waterPacketBackingBytes: packet.backingBytes,
				waterCompressedBytes: packet.compressedBytes,
				contextStates: history.contexts.states,
				contextDataBackingBytes: history.retainedDataBackingBufferBytes,
				frozenLocalGridOrMapsReused: false,
				everyEndpointRecomputed: true,
				resumedCompletedOrigins: [...restoredOrigins],
				resumedMaps: phases
					.slice(0, restoredOrigins.size)
					.reduce(
						(total, phase) =>
							total +
							("productions" in phase ? phase.productions.length + 1 : 0),
						0,
					),
				endpointArtifactsIdenticalToPrevious: access.rows.filter(
					(row: { output: unknown }, i: number) =>
						JSON.stringify(row.output) ===
						JSON.stringify(priorAccess.rows[i].output),
				).length,
				roadTimeComparisonScope:
					"Diagnostic comparisons only; fresh source POST IDs, paid geometry and endpoint choices change. No identical-attachment or graph-optimum monotonicity assumption; retain every increase.",
				retainedBackingBytes:
					afterLoad.arrayBuffers - baselineMemory.arrayBuffers,
				retainedBackingGatePassed:
					afterLoad.arrayBuffers - baselineMemory.arrayBuffers <= 162238546,
				providerRequests: outboundCalls,
				baselineMemory,
				afterLoad,
				afterQueries: await assertPhaseReleased(
					afterLoad.arrayBuffers,
					"after all initial access fields/displays",
				),
				hostTotalMs: performance.now() - began,
				candidateAdmitted: false,
				pending: [
					"All166 complete road/local path witnesses and physical/source/shore checks",
					"Full app/package/retained/startup/API/shared-camera gates",
				],
				scope:
					"One benchmark of the audited mandatory-turn graph with the established renderer, reference routes and release thresholds. The renderer, prices, geography and endpoint policies are fixed. All endpoints and maps use the same candidate. Three completed origins resume from checksum verified files. The incomplete fourth origin is recomputed. Road-time deltas are diagnostic across the two graphs. Host time includes loading, rendering, validation and writes. Release and app packaging are separate.",
			};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, numericalGatesPassed: report.numericalGatesPassed, overall: report.overall, commonFiniteComparison: report.commonFiniteComparison, gates: report.gates, hostTotalMs: report.hostTotalMs })}\n`,
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
