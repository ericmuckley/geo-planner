/** Single-use fixed national display profile; no provider times or fitting. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { writeFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
	bit,
	DIRECTIONS,
	hasLink,
	nibble,
} from "./coarse_osm_display_grid_v1.ts";
import { filledDisplay } from "./coarse_osm_filled_display_v1.ts";
import {
	connectOrigin,
	type OriginConnection,
	type OriginGeography,
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

const repo = path.resolve(import.meta.dirname, "..");
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
function phase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	access: OriginConnection,
	id: string,
	minutes: number,
	root: string,
	check: () => void,
) {
	const started = performance.now();
	const field = computeRoadField(
		graph,
		geometry,
		access.snap,
		access.connectorTicks,
		{ maxTicks: minutes * 480, check },
	);
	const fieldMs = performance.now() - started;
	const labelSha = sha(new Uint8Array(field.labels.buffer));
	const vertexSha = sha(new Uint8Array(field.vertexArrivalSeconds.buffer));
	const witnesses = {
		localCells: 0,
		roadSeeds: 0,
		inputSeeds: 0,
		exactParentLinks: 0,
	};
	const display = filledDisplay(graph, geometry, geography, access, field, {
		check,
		probe: (g) => {
			for (let i = 0; i < g.times.length; i++)
				if (g.times[i] !== 65535) {
					assert.ok(bit(g.land, i));
					assert.ok(g.times[i] <= minutes * 60);
					witnesses.localCells++;
					const d = nibble(g.parents, i);
					if (d === 8) {
						witnesses.roadSeeds++;
						continue;
					}
					if (d === 9) {
						witnesses.inputSeeds++;
						continue;
					}
					assert.ok(d < 8);
					const [dx, dy] = DIRECTIONS[d],
						x = i % g.frame.width,
						y = Math.floor(i / g.frame.width),
						nx = x + dx,
						ny = y + dy;
					assert.ok(
						nx >= 0 && nx < g.frame.width && ny >= 0 && ny < g.frame.height,
					);
					const j = ny * g.frame.width + nx;
					assert.ok(hasLink(g.links, i, j, d));
					const cost =
						dy === 0
							? g.horizontal[y]
							: dx === 0
								? g.vertical
								: g.diagonal[Math.min(y, ny)];
					assert.equal(g.times[i], g.times[j] + cost);
					assert.ok(g.times[j] < g.times[i]);
					witnesses.exactParentLinks++;
				}
		},
	});
	assert.equal(sha(new Uint8Array(field.labels.buffer)), labelSha);
	assert.equal(
		sha(new Uint8Array(field.vertexArrivalSeconds.buffer)),
		vertexSha,
	);
	assert.equal(witnesses.localCells, display.stats.localCells);
	assert.ok(display.frame.step >= 5000 && display.frame.step <= 25000);
	assert.ok(
		display.stats.maximumBackingBufferBytes <= 67108864 &&
			display.stats.jsonBytes <= 3000000,
	);
	assert.ok(display.stats.selectedCells > 0 && display.stats.vertices > 0);
	const json = JSON.stringify(display.output),
		filename = `${id}-${minutes}.geojson`;
	writeFileSync(path.join(root, filename), json, { flag: "wx" });
	return {
		sourceId: id,
		minutes,
		frame: display.frame,
		fieldMs,
		fieldStats: field.stats,
		stats: display.stats,
		witnesses,
		output: {
			filename,
			bytes: Buffer.byteLength(json),
			sha256: sha(Buffer.from(json)),
		},
		fieldLabelsUnchanged: true,
		vertexSummariesRestored: true,
		phaseMs: performance.now() - started,
	};
}

async function main() {
	const began = performance.now(),
		[recipeName, pin] = process.argv.slice(2);
	assert.ok(recipeName && pin && global.gc);
	const bytes = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(bytes), pin);
	const plan = JSON.parse(bytes.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-car-filled-display-profile-v1",
	);
	assert.equal(plan.controlsPassed, 8);
	assert.deepEqual(plan.horizonsMinutes, [120, 360, 600, 720]);
	assert.equal(plan.sources.length, 8);
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
	await writeFile(path.join(root, "execution-plan.json"), bytes, {
		flag: "wx",
	});
	const check = () => {
		assert.ok(
			performance.now() - began < plan.hostSeconds * 1000,
			"Display host deadline",
		);
		assert.ok(
			process.memoryUsage().rss < 4 * 1024 ** 3,
			"Display host RSS bound",
		);
	};
	try {
		const baseline = await settledPhaseMemory(),
			firstBegan = performance.now();
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
		const afterLoad = await settledPhaseMemory();
		const rows = [];
		let firstLoadConnectionFieldDisplayMs = 0;
		for (const source of plan.sources) {
			const connected = connectOrigin(
				core.graph,
				paid.geometry,
				core.keys,
				core.starts,
				geo.geography,
				source.coordinate,
				check,
			);
			assert.ok(connected.connection);
			for (const minutes of plan.horizonsMinutes) {
				check();
				const summary = phase(
					core.graph,
					paid.geometry,
					geo.geography,
					connected.connection,
					source.id,
					minutes,
					root,
					check,
				);
				const released = await assertPhaseReleased(
					afterLoad.arrayBuffers,
					"after display/field summary function",
				);
				if (!rows.length)
					firstLoadConnectionFieldDisplayMs = performance.now() - firstBegan;
				const row = { ...summary, afterRelease: released };
				rows.push(row);
				await writeFile(
					path.join(root, `${source.id}-${minutes}.json`),
					`${JSON.stringify(row, null, 2)}\n`,
					{ flag: "wx" },
				);
				process.stdout.write(
					`${JSON.stringify({ sourceId: source.id, minutes, step: summary.frame.step / 1e6, cells: summary.frame.width * summary.frame.height, displayMs: summary.stats.displayMs, phaseMs: summary.phaseMs })}\n`,
				);
			}
		}
		assert.equal(rows.length, 32);
		const afterQueries = await assertPhaseReleased(
			afterLoad.arrayBuffers,
			"after all displays",
		);
		const report = {
			status: "host_national_filled_display_software_profile_passed",
			recipeSha256: pin,
			fieldsAndDisplays: 32,
			rows,
			baseline,
			afterLoad,
			afterQueries,
			hostFirstLoadConnectionFieldDisplayMsIncludingGc:
				firstLoadConnectionFieldDisplayMs,
			hostTotalMs: performance.now() - began,
			maximumDisplayBackingBufferBytes: Math.max(
				...rows.map((row) => row.stats.maximumBackingBufferBytes),
			),
			scope:
				"Host software/source display profile, all eight fixed sources at 2/6/10/12h. Local parent sums and field restoration checked; all outputs retained. First scope includes hashes, probe validation, output write/release/GC. Host RSS guard is not a cgroup/zero-swap/CPU isolation measurement. No reference times, full road path reconstruction, accuracy, complete app, packaged startup, cloud or production switch.",
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, fieldsAndDisplays: 32, firstMs: firstLoadConnectionFieldDisplayMs, hostTotalMs: report.hostTotalMs })}\n`,
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
