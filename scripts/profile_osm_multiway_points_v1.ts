/** All83 primary-finish context feasibility; frozen local-grid/maps, no admission. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import type { PointTiming } from "./coarse_osm_access_timing_v2.ts";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import { withDiagnosticContextRoadField } from "./coarse_osm_context_road_field_v1.ts";
import { numericalGates } from "./coarse_osm_display_gates_v1.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { paidTerminalArrival } from "./coarse_osm_terminal_access_v1.ts";
import { timingRow } from "./coarse_osm_timing_rows_v2.ts";
import type { TimingRow } from "./coarse-damped-gates.ts";

type Place = { lon: number; lat: number };
type Sample = TimingRow & {
	id: string;
	origin: Place;
	destination: Place;
	valhallaMinutes: number | null;
};
type Input = { coordinate: Coordinate; connection: OriginConnection | null };
type ChoiceAsset = {
	filename: string;
	rawBytes: number;
	rawSha256: string;
	compressedBytes: number;
	sha256: string;
};
type AccessRow = {
	coordinate: Coordinate;
	supported: boolean;
	output: ChoiceAsset;
};
const repo = path.resolve(import.meta.dirname, ".."),
	sha = (b: Uint8Array) => createHash("sha256").update(b).digest("hex"),
	xy = (p: Place): Coordinate => [p.lon, p.lat],
	key = (p: Coordinate) => JSON.stringify(p);

async function main() {
	const began = performance.now(),
		[name, pin] = process.argv.slice(2);
	assert.ok(name && pin && global.gc);
	const raw = await readFile(path.resolve(repo, name));
	assert.equal(sha(raw), pin);
	const plan = JSON.parse(raw.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-multiway-point-profile-v1",
	);
	assert.equal(plan.controlsPassed, 14);
	assert.equal(plan.hostSeconds, 300);
	assert.equal(plan.maxOwnedBytes, 8388608);
	assert.ok(
		plan.priorReserveBytes +
			plan.newClosedAllocationBytes +
			plan.metadataScratchReserveBytes +
			plan.maxOwnedBytes <
			72 * 1024 ** 3,
	);
	for (const [file, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, file))), expected, file);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), raw, { flag: "wx" });
	let outbound = 0;
	globalThis.fetch = async () => {
		outbound++;
		throw new Error("Unexpected outbound request");
	};
	const check = () => {
		assert.ok(performance.now() - began < 300000);
		assert.ok(process.memoryUsage().rss < 4 * 1024 ** 3);
	};
	try {
		const previous = JSON.parse(
			await readFile(path.join(repo, plan.candidate), "utf8"),
		) as {
			rows: Sample[];
			phases: {
				origin: Coordinate;
				diagnostic: { timings: Record<string, PointTiming> };
			}[];
		};
		assert.equal(previous.rows.length, 83);
		assert.equal(
			previous.rows.filter((r) => r.valhallaMinutes !== null).length,
			35,
		);
		// IDs/costs/flags/geometry remain identical; only source-supported turn pairs replace entry bans.
		const oldCore = JSON.parse(
			await readFile(
				path.join(repo, plan.parentCoreSource, "manifest.json"),
				"utf8",
			),
		);
		const newCore = JSON.parse(
			await readFile(path.join(repo, plan.coreSource, "manifest.json"), "utf8"),
		);
		assert.equal(newCore.requiresTurnContextSearch, true);
		let identical = 0;
		for (const [name, field] of Object.entries(oldCore.fields)) {
			if (name === "routing/forbidden-turns.u24") continue;
			assert.deepEqual(newCore.fields[name], field);
			identical++;
		}
		assert.equal(identical, 12);
		const inputs = JSON.parse(
			await readFile(path.join(repo, plan.connections), "utf8"),
		) as Input[];
		const access = JSON.parse(
			await readFile(path.join(repo, plan.accessReport), "utf8"),
		) as { rows: AccessRow[]; totalConnections: number };
		assert.equal(inputs.length, 79);
		assert.equal(access.rows.length, 79);
		const byPoint = new Map(
			inputs.map((r) => [key(r.coordinate), r.connection]),
		);
		const assets = new Map(access.rows.map((r) => [key(r.coordinate), r]));
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
		assert.equal(history.contexts.states, 34101);
		assert.equal(history.retainedDataBackingBufferBytes, 1784491);
		const afterLoad = await settledPhaseMemory();
		function choices(point: Coordinate) {
			const row = assets.get(key(point));
			assert.ok(row?.supported);
			const asset = row.output;
			assert.match(asset.filename, /^endpoint-\d{2}\.json\.gz$/);
			const bytes = readFileSync(
				path.join(repo, plan.accessSource, asset.filename),
			);
			assert.equal(bytes.length, asset.compressedBytes);
			assert.equal(sha(bytes), asset.sha256);
			const decoded = gunzipSync(bytes, { maxOutputLength: 4194304 });
			assert.equal(decoded.length, asset.rawBytes);
			assert.equal(sha(decoded), asset.rawSha256);
			return JSON.parse(decoded.toString("utf8")) as OriginConnection[];
		}
		function originPhase(phase: (typeof previous.phases)[number]) {
			check();
			const start = performance.now(),
				source = byPoint.get(key(phase.origin));
			assert.ok(source);
			const starts = accessStarts(source, choices(phase.origin));
			const cases = previous.rows.filter(
				(r) => key(xy(r.origin)) === key(phase.origin),
			);
			const targets = cases.map((sample) => {
				const target = xy(sample.destination),
					primary = byPoint.get(key(target));
				assert.ok(primary);
				return { primary };
			});
			const timed = withDiagnosticContextRoadField(
				core.graph,
				paid.geometry,
				history.contexts,
				starts,
				(field) => ({
					finishes: targets.map((target) => {
						check();
						return paidTerminalArrival(core.graph, paid.geometry, field, [
							target.primary,
						]);
					}),
					fieldStats: { ...field.stats },
				}),
				{ maxTicks: 432000, check },
			);
			const rows = [],
				comparisons = [];
			for (const [index, sample] of cases.entries()) {
				const frozen = phase.diagnostic.timings[sample.id];
				assert.ok(frozen);
				const best = timed.finishes[index];
				const ticks = Math.min(
					best?.ticks ?? Infinity,
					frozen.localGridTicks ?? Infinity,
				);
				const point = Number.isFinite(ticks) ? ticks : null;
				rows.push(
					timingRow(
						{ ...sample, candidate: sample.baseline },
						point,
						sample.candidate.predictedReachable,
					),
				);
				comparisons.push({
					id: sample.id,
					previousPointTicks: frozen.ticks,
					pointTicks: point,
					previousRoadTicks: frozen.roadTicks,
					bestRoadTicks: best?.ticks ?? null,
					frozenLocalGridTicks: frozen.localGridTicks,
					frozenPublicShaded: sample.candidate.predictedReachable,
				});
			}
			return {
				origin: phase.origin,
				rows,
				comparisons,
				fieldStats: timed.fieldStats,
				hostFieldAndFinishesMs: performance.now() - start,
			};
		}
		const phases = [],
			rows: Sample[] = [],
			comparisons = [];
		for (const phase of previous.phases) {
			const result = originPhase(phase);
			phases.push(result);
			rows.push(...result.rows);
			comparisons.push(...result.comparisons);
			const released = await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after context field",
			);
			await writeFile(
				path.join(
					root,
					`origin-${String(phases.length).padStart(2, "0")}.json`,
				),
				`${JSON.stringify({ ...result, afterReleaseArrayBuffers: released.arrayBuffers }, null, 2)}\n`,
				{ flag: "wx" },
			);
		}
		assert.equal(rows.length, 83);
		assert.deepEqual(
			rows.map((r) => r.id).sort(),
			previous.rows.map((r) => r.id).sort(),
		);
		for (const row of rows)
			assert.deepEqual(
				row.baseline,
				previous.rows.find((r) => r.id === row.id)?.baseline,
			);
		assert.equal(phases.length, 21);
		assert.equal(outbound, 0);
		const report = {
			status: "all83_multiway_primary_finish_context_feasibility_complete",
			recipeSha256: pin,
			...numericalGates(rows),
			rows,
			comparisons,
			phases,
			originalCases: 83,
			valhallaCases: 35,
			roadArrivalRegressions: comparisons.filter(
				(r) =>
					r.previousRoadTicks !== null &&
					(r.bestRoadTicks === null || r.bestRoadTicks > r.previousRoadTicks),
			).length,
			graphSupersetDoesNotGuaranteeNewAccessQueryMonotonicity: true,
			changedPointTimes: comparisons.filter(
				(r) => r.pointTicks !== r.previousPointTicks,
			).length,
			roadFinishesImproved: comparisons.filter(
				(r) =>
					r.bestRoadTicks !== null &&
					(r.previousRoadTicks === null ||
						r.bestRoadTicks < r.previousRoadTicks),
			).length,
			heldCoreGeometryContextsBackingBytes:
				afterLoad.arrayBuffers - baseline.arrayBuffers,
			afterLoad,
			afterQueries: await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after context prototype",
			),
			contextStates: history.contexts.states,
			contextDataBackingBytes: history.retainedDataBackingBufferBytes,
			coreLoadMs: core.loadMsIncludingReadsHashesInflateDecodeAndValidation,
			geometryLoadMs: paid.loadMsIncludingReadsHashesInflateDecodeAndValidation,
			contextLoadMs: history.loadMsIncludingReadsHashesInflateAndValidation,
			maximumQueryBackingBytes: Math.max(
				...phases.map((p) => p.fieldStats.maximumBackingBufferBytes),
			),
			providerRequests: outbound,
			hostTotalMs: performance.now() - began,
			candidateAdmitted: false,
			scope:
				"Point-only feasibility on all83/35 frozen cases. NEW physical IDs/paid geometry/new79 access collections. Source prices/flags/initial-access policy/primary destination full-connector semantics unchanged. Single-via histories and static source-plus-multi-entry bans stay. Endpoint choices may change,so all road regressions/nulls retained and reported;graph path superset alone does not imply query monotonicity. Frozen prior local-grid timings/public map classifications explicitly reused: diagnostic numerical proxy only, no new candidate/maps/166sum/shape/physical/app admission. No terminal-alternatives or speed policy. All numeric ID inputs are from this new graph;12 physical core fields match the new access core byte-for-byte. Core/geometry/context backing excludes geography/water/display/app; host total includes binding/load/21 fields/scalars/output/GC, not packaged first estimate/search-only/cloud. RSS/deadline only, no cgroup/CPU/swap admission.",
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, changedPointTimes: report.changedPointTimes, roadFinishesImproved: report.roadFinishesImproved, overall: report.overall, gates: report.gates, hostTotalMs: report.hostTotalMs })}\n`,
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
