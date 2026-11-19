/** All83 fixed-field terminal-choice feasibility screen; no map rerender or admission. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import { computeDiagnosticAccessRoadField } from "./coarse_osm_access_road_field_v2.ts";
import type { PointTiming } from "./coarse_osm_access_timing_v2.ts";
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
		"data/coarse-quality/us-osm-terminal-alternatives-profile-v1",
	);
	assert.equal(plan.controlsPassed, 10);
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
			const field = computeDiagnosticAccessRoadField(
				core.graph,
				paid.geometry,
				starts,
				{ maxTicks: 432000, check },
			);
			const cases = previous.rows.filter(
				(r) => key(xy(r.origin)) === key(phase.origin),
			);
			const rows = [],
				comparisons = [];
			for (const sample of cases) {
				check();
				const target = xy(sample.destination),
					primary = byPoint.get(key(target));
				assert.ok(primary);
				const alternatives = choices(target);
				accessStarts(primary, alternatives);
				const frozen = phase.diagnostic.timings[sample.id];
				assert.ok(frozen);
				const original = paidTerminalArrival(core.graph, paid.geometry, field, [
					primary,
				]);
				assert.equal(
					original?.ticks ?? null,
					frozen.roadTicks,
					"Same primary must reproduce frozen road timing",
				);
				const best = paidTerminalArrival(
					core.graph,
					paid.geometry,
					field,
					alternatives,
				);
				assert.ok(
					original === null || (best !== null && best.ticks <= original.ticks),
				);
				const ticks = Math.min(
					best?.ticks ?? Infinity,
					frozen.localGridTicks ?? Infinity,
				);
				const point = Number.isFinite(ticks) ? ticks : null;
				assert.ok(
					frozen.ticks === null || (point !== null && point <= frozen.ticks),
				);
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
					terminalChoices: alternatives.length,
					winningTerminal: best === null ? null : alternatives[best.index],
				});
			}
			return {
				origin: phase.origin,
				rows,
				comparisons,
				fieldStats: field.stats,
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
			await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after terminal alternatives field",
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
			status: "all83_fixed_field_terminal_alternatives_prototype_complete",
			recipeSha256: pin,
			...numericalGates(rows),
			rows,
			comparisons,
			phases,
			originalCases: 83,
			valhallaCases: 35,
			primaryRoadTimingsReproduced: 83,
			changedPointTimes: comparisons.filter(
				(r) => r.pointTicks !== r.previousPointTicks,
			).length,
			roadFinishesImproved: comparisons.filter(
				(r) =>
					r.bestRoadTicks !== null &&
					(r.previousRoadTicks === null ||
						r.bestRoadTicks < r.previousRoadTicks),
			).length,
			heldCoreGeometryBackingBytes:
				afterLoad.arrayBuffers - baseline.arrayBuffers,
			afterLoad,
			afterQueries: await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after terminal prototype",
			),
			providerRequests: outbound,
			hostTotalMs: performance.now() - began,
			candidateAdmitted: false,
			scope:
				"Feasibility only on all83/35 frozen cases. Same graph/geometry/source prices/initial starts/caps and prequalified land-safe access collections; every primary road timing must match. Only terminal choice minimized with its full connector price. Existing local-grid timings and public shape classifications reused explicitly, no map rerender/new field model/cost fit. Original accuracy/physical/166sum/shape/app gates retained, numerical summary diagnostic only. Core/geometry backing excludes geography/water/display/app; host RSS/deadline not cgroup/CPU/swap/cloud admission.",
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
