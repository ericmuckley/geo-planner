import assert from "node:assert/strict";
import test from "node:test";
import { diagnosticAccessFilledDisplay } from "./coarse_osm_access_display_v3.ts";
import { geography, rectangle } from "./coarse_osm_access_fixture_v2.ts";
import {
	accessDisplayPointTiming,
	type PointTiming,
} from "./coarse_osm_access_timing_v2.ts";
import {
	finishAccessPointTiming,
	type PreparedPointTiming,
	prepareAccessPointTiming,
} from "./coarse_osm_access_timing_v3.ts";
import { contextDisplayFixture } from "./coarse_osm_context_display_fixture_v1.ts";
import { withDiagnosticContextRoadField } from "./coarse_osm_context_road_field_v1.ts";
import type { DisplayOptions } from "./coarse_osm_filled_display_v1.ts";
import { settledPhaseMemory } from "./coarse_osm_phase_lifetime_v1.ts";
import { reusedContextDisplay as previousDisplay } from "./coarse_osm_reused_display_v1.ts";
import { reusedContextDisplay } from "./coarse_osm_reused_display_v2.ts";
import { legacyRoutingGeography } from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV6 } from "./coarse_osm_routing_geography_v6.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { waterFixture } from "./coarse_osm_water_routing_fixture_v1.ts";

test("initial seed pressure coarsens before consumption while reusing one raster", async () => {
	const p = contextDisplayFixture(
		[
			[0, 0.0025],
			[2, 0.0025],
			[4, 0.0025],
			[6, 0.0025],
		],
		[
			[0, 1, 1000],
			[1, 2, 1000],
			[2, 3, 1000],
		],
	);
	const geo = legacyRoutingGeography({
		bounds: [-0.1, 0, 6.1, 0.005],
		boundary: [[rectangle(-0.1, 0, 6.1, 0.005)]],
		lakes: [],
	});
	const starts = [{ position: p.source.snap, initialTicks: 0 }];
	const options = { maxTicks: 4800, heapEntries: 1000 };
	assert.throws(
		() =>
			previousDisplay(
				p.graph,
				p.geometry,
				p.contexts,
				geo,
				p.source,
				starts,
				options,
				true,
			),
		/local heap capacity/,
	);
	const baseline = await settledPhaseMemory();
	const buffers: WeakRef<ArrayBufferLike>[] = [];
	let peak = 0;
	const result = reusedContextDisplay(
		p.graph,
		p.geometry,
		p.contexts,
		geo,
		p.source,
		starts,
		{
			...options,
			observeBacking: (backing) => {
				peak = Math.max(
					peak,
					process.memoryUsage().arrayBuffers - baseline.arrayBuffers,
				);
				buffers.push(...backing.map((b) => new WeakRef(b)));
			},
		},
		true,
	);
	assert.equal(result.stats.retries.length, 1);
	assert.equal(result.stats.retries[0].finiteSeedCells, 1001);
	assert.equal(result.frame.step, 6250);
	assert.ok(result.stats.initialSeedCells <= 1000);
	assert.ok(result.stats.maximumHeapEntries <= 1000);
	assert.ok(peak > 0 && peak <= result.stats.maximumBackingBufferBytes);
	await settledPhaseMemory();
	assert.ok((await settledPhaseMemory()).arrayBuffers <= baseline.arrayBuffers);
	assert.ok(buffers.every((b) => b.deref() === undefined));
});

test("exhausted seed retries refuse and release the unconsumed field", async () => {
	const p = contextDisplayFixture(
		[
			[0, 0.0025],
			[2, 0.0025],
			[4, 0.0025],
			[6, 0.0025],
		],
		[
			[0, 1, 100],
			[1, 2, 100],
			[2, 3, 100],
		],
	);
	const geo = legacyRoutingGeography({
		bounds: [-0.1, -1, 6.1, 1],
		boundary: [[rectangle(-0.1, -1, 6.1, 1)]],
		lakes: [],
	});
	const observed: WeakRef<ArrayBufferLike>[] = [];
	const baseline = await settledPhaseMemory();
	assert.throws(
		() =>
			reusedContextDisplay(
				p.graph,
				p.geometry,
				p.contexts,
				geo,
				p.source,
				[{ position: p.source.snap, initialTicks: 0 }],
				{
					maxTicks: 4800,
					heapEntries: 32,
					beforeSeed: (field) =>
						observed.push(
							new WeakRef(field.labels.buffer),
							new WeakRef(field.vertexArrivalSeconds.buffer),
							new WeakRef(field.seeds.buffer),
						),
				},
				true,
			),
		/initial finite seeds exceed local heap capacity/,
	);
	await settledPhaseMemory();
	const after = await settledPhaseMemory();
	assert.ok(after.arrayBuffers <= baseline.arrayBuffers);
	assert.equal(observed.length, 3);
	assert.ok(observed.every((b) => b.deref() === undefined));
});

function snapshot(grid: Parameters<NonNullable<DisplayOptions["probe"]>>[0]) {
	const n = grid.frame.width * grid.frame.height;
	return {
		frame: grid.frame,
		times: Array.from(grid.times),
		parents: Array.from(grid.parents.subarray(0, Math.ceil(n / 2))),
		links: Array.from(grid.links.subarray(0, Math.ceil(n / 2))),
		land: Array.from(grid.land.subarray(0, Math.ceil(n / 8))),
		coverage: Array.from(grid.coverage.subarray(0, Math.ceil(n / 8))),
		boundary: Array.from(grid.boundary.subarray(0, Math.ceil(n / 8))),
	};
}

function compareWithOld(
	p: ReturnType<typeof contextDisplayFixture>,
	geo: Parameters<typeof reusedContextDisplay>[3],
) {
	const starts = [{ position: p.source.snap, initialTicks: 0 }];
	const foot = p.graph.coordinate(1);
	const targets: { target: Coordinate; connection: typeof p.source | null }[] =
		[
			{ target: p.source.origin, connection: p.source },
			{
				target: foot,
				connection: {
					...p.source,
					origin: foot,
					snap: { ...p.source.snap, segmentFraction: 1, coordinate: foot },
				},
			},
			{ target: [-0.02, 0.02], connection: null },
			{ target: [0.5, 0.5], connection: null },
		];
	let oldTimings: PointTiming[] = [];
	let nextTimings: PointTiming[] = [];
	let prepared: PreparedPointTiming[] = [];

	let oldGrid: ReturnType<typeof snapshot> | undefined;
	let newGrid: ReturnType<typeof snapshot> | undefined;
	const before = Object.fromEntries(
		Object.entries(p.raw).map(([k, v]) => [k, v.slice()]),
	);
	const old = withDiagnosticContextRoadField(
		p.graph,
		p.geometry,
		p.contexts,
		starts,
		(field) =>
			diagnosticAccessFilledDisplay(p.graph, p.geometry, geo, p.source, field, {
				maxCells: 10000,
				heapEntries: 1000,
				probe: (grid) => {
					oldGrid = snapshot(grid);
					oldTimings = targets.map((t) =>
						accessDisplayPointTiming(
							p.graph,
							p.geometry,
							geo,
							field,
							grid,
							p.source.origin,
							t.target,
							t.connection,
						),
					);
				},
			}),
		{ maxTicks: 4800, maxHeapEntries: 1000 },
	);
	const next = reusedContextDisplay(
		p.graph,
		p.geometry,
		p.contexts,
		geo,
		p.source,
		starts,
		{
			maxTicks: 4800,
			maxCells: 10000,
			heapEntries: 1000,
			beforeSeed: (field) => {
				prepared = targets.map((t) =>
					prepareAccessPointTiming(
						p.graph,
						p.geometry,
						field,
						p.source.origin,
						t.target,
						t.connection,
					),
				);
			},
			probe: (grid) => {
				newGrid = snapshot(grid);
				nextTimings = prepared.map((t) =>
					finishAccessPointTiming(geo, grid, t),
				);
			},
		},
		true,
	);
	assert.deepEqual(next.frame, old.frame);
	assert.deepEqual(newGrid, oldGrid);
	assert.deepEqual(nextTimings, oldTimings);
	assert.deepEqual(next.output, old.output);
	assert.deepEqual(p.raw, before);
	assert.ok(next.stats.maximumBackingBufferBytes <= 67108864);
}

for (const lake of [false, true]) {
	test(`same-resolution times/parents/coverage/masks/maps match with lake=${lake}`, () => {
		const p = contextDisplayFixture(
			[
				[0, 0],
				[0.02, 0],
				[0.04, 0],
				[0.06, 0.02],
			],
			[
				[0, 1, 500],
				[1, 2, 500],
				[2, 3, 500],
			],
			[[10, 20, 30]],
		);
		const geo = legacyRoutingGeography(
			geography(lake ? [[rectangle(0.012, -0.004, 0.024, 0.004)]] : []),
		);
		compareWithOld(p, geo);
	});
}

test("label and vertex buffers are actually reused on a larger synthetic chain", async () => {
	const points: Coordinate[] = Array.from({ length: 5001 }, (_, i) => [
		(i * 0.04) / 5000,
		0,
	]);
	const p = contextDisplayFixture(
		points,
		Array.from({ length: 5000 }, (_, i) => [i, i + 1, 1000]),
	);
	const geo = legacyRoutingGeography(geography());
	const owned: WeakRef<ArrayBufferLike>[] = [];
	const observeBacking = (buffers: ArrayBufferLike[]) =>
		owned.push(...buffers.map((b) => new WeakRef(b)));
	const base = await settledPhaseMemory();
	const result = reusedContextDisplay(
		p.graph,
		p.geometry,
		p.contexts,
		geo,
		p.source,
		[{ position: p.source.snap, initialTicks: 0 }],
		{ maxTicks: 4800, maxCells: 10000, heapEntries: 64, observeBacking },
	);
	assert.ok(result.stats.reusedLabelBytes > 0);
	assert.ok(result.stats.reusedVertexBytes > 0);
	await settledPhaseMemory();
	assert.ok((await settledPhaseMemory()).arrayBuffers <= base.arrayBuffers);
	assert.ok(owned.length >= 8);
	assert.ok(owned.every((ref) => ref.deref() === undefined));
});

test("an exception after buffer consumption releases all query storage", async () => {
	const p = contextDisplayFixture(
		[
			[0, 0],
			[0.04, 0],
		],
		[[0, 1, 1000]],
	);
	const geo = legacyRoutingGeography(geography());
	const before = Object.fromEntries(
		Object.entries(p.raw).map(([k, v]) => [k, v.slice()]),
	);
	const owned: WeakRef<ArrayBufferLike>[] = [];
	const observeBacking = (buffers: ArrayBufferLike[]) =>
		owned.push(...buffers.map((b) => new WeakRef(b)));
	const base = await settledPhaseMemory();
	assert.throws(
		() =>
			reusedContextDisplay(
				p.graph,
				p.geometry,
				p.contexts,
				geo,
				p.source,
				[{ position: p.source.snap, initialTicks: 0 }],
				{
					maxTicks: 4800,
					maxCells: 10000,
					heapEntries: 1000,
					observeBacking,
					probe: () => {
						throw new Error("post-consume stop");
					},
				},
			),
		/post-consume stop/,
	);
	await settledPhaseMemory();
	const released = await settledPhaseMemory();
	process.stdout.write(
		`${JSON.stringify({ probeExceptionBackingDelta: released.arrayBuffers - base.arrayBuffers, remaining: owned.map((r, i) => ({ i, bytes: r.deref()?.byteLength ?? 0 })).filter((x) => x.bytes > 0) })}\n`,
	);
	assert.ok(released.arrayBuffers <= base.arrayBuffers);
	assert.ok(owned.length >= 8);
	assert.ok(owned.every((ref) => ref.deref() === undefined));
	assert.deepEqual(p.raw, before);
});

for (const uncertain of [false, true]) {
	test(`source-water and uncertainty semantics match at the same resolution: ${uncertain}`, async () => {
		const packet = await waterFixture(
			(x, y) => x >= 22 && x <= 24 && y >= 19 && y <= 21,
			(x, y) => uncertain && x >= 23 && x <= 25 && y >= 18 && y <= 22,
		);
		const p = contextDisplayFixture(
			[
				[0, 0],
				[0.04, 0],
			],
			[[0, 1, 1000]],
		);
		const geo = waterRoutingGeographyV6(
			geography([[rectangle(0.018, -0.003, 0.023, 0.003)]]),
			packet.current,
		);
		compareWithOld(p, geo);
	});
}
