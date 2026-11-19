import assert from "node:assert/strict";
import test from "node:test";
import { rectangle } from "./coarse_osm_access_fixture_v2.ts";
import {
	finishAccessPointTiming,
	prepareAccessPointTiming,
} from "./coarse_osm_access_timing_v3.ts";
import { addPaidBoundaryCoverage } from "./coarse_osm_boundary_coverage_v1.ts";
import { boundaryContextDisplay } from "./coarse_osm_boundary_display_v1.ts";
import { contextDisplayFixture } from "./coarse_osm_context_display_fixture_v1.ts";
import { bit, center, setBit } from "./coarse_osm_display_grid_v3.ts";
import type { DisplayProbe } from "./coarse_osm_filled_display_v1.ts";
import { connectorPrice } from "./coarse_osm_origin_connections_v2.ts";
import { settledPhaseMemory } from "./coarse_osm_phase_lifetime_v1.ts";
import { reusedContextDisplay } from "./coarse_osm_reused_display_v2.ts";
import {
	landConnection,
	legacyRoutingGeography,
} from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV6 } from "./coarse_osm_routing_geography_v6.ts";
import { waterFixture } from "./coarse_osm_water_routing_fixture_v1.ts";

function grid(width = 3, height = 1): DisplayProbe {
	const n = width * height;
	return {
		frame: { west: 0, south: 0, step: 5000, width, height },
		times: new Uint16Array(n).fill(65535),
		parents: new Uint8Array(Math.ceil(n / 2)).fill(255),
		links: new Uint8Array(Math.ceil(n / 2)),
		land: new Uint8Array(Math.ceil(n / 8)),
		coverage: new Uint8Array(Math.ceil(n / 8)),
		boundary: new Uint8Array(Math.ceil(n / 8)),
		horizontal: new Uint16Array(height),
		diagonal: new Uint16Array(height),
		vertical: 1,
	};
}
const geo = (lakes: number[][][][] = []) =>
	legacyRoutingGeography({
		bounds: [-0.01, -0.01, 0.03, 0.03],
		boundary: [[rectangle(-0.01, -0.01, 0.03, 0.03)]],
		lakes,
	});
const shore = () => geo([[rectangle(0.007, -0.01, 0.03, 0.03)]]);
function source(g: DisplayProbe, cell = 0, seconds = 20) {
	g.times[cell] = seconds;
	setBit(g.land, cell);
	setBit(g.coverage, cell);
}
function unchanged(g: DisplayProbe) {
	return Object.fromEntries(
		Object.entries(g)
			.filter(([name]) => name !== "coverage")
			.map(([name, value]) => [
				name,
				ArrayBuffer.isView(value) ? Array.from(value as Uint8Array) : value,
			]),
	);
}

test("partial dry cell requires its full paid connector at the exact horizon", () => {
	const g = grid();
	source(g);
	const from = center(g.frame, 0);
	const to: [number, number] = [0.00625, 0.00125];
	const price = Math.ceil(connectorPrice(from, to).ticks / 8);
	assert.ok(price > 0);
	const before = unchanged(g);
	assert.equal(
		addPaidBoundaryCoverage(shore(), g, 20 + price - 1).addedCells,
		0,
	);
	let witnesses = 0;
	const stats = addPaidBoundaryCoverage(
		shore(),
		g,
		20 + price,
		undefined,
		(w) => {
			witnesses++;
			assert.equal(w.cell, 1);
			assert.equal(w.fromCell, 0);
			assert.equal(
				w.connectorSeconds,
				Math.ceil(connectorPrice(w.from, w.to).ticks / 8),
			);
			assert.ok(w.fromSeconds + w.connectorSeconds <= 20 + price);
			assert.ok(landConnection(shore(), [...w.from], [...w.to]));
			assert.ok(landConnection(shore(), [...w.to], [...w.to]));
		},
	);
	assert.equal(stats.addedCells, 1);
	assert.equal(witnesses, 1);
	assert.equal(bit(g.coverage, 1), 1);
	assert.equal(bit(g.coverage, 2), 0);
	assert.deepEqual(unchanged(g), before);
});

test("a dry island across a water barrier cannot receive coverage", () => {
	const g = grid();
	source(g);
	const islands = geo([
		[rectangle(0.004, -0.01, 0.005, 0.03)],
		[rectangle(0.0074, -0.01, 0.0076, 0.03)],
	]);
	assert.ok(landConnection(islands, [0.00625, 0.00125], [0.00625, 0.00125]));
	assert.equal(addPaidBoundaryCoverage(islands, g, 1000).addedCells, 0);
	assert.equal(bit(g.coverage, 1), 0);
});

test("water and fallback-closed samples remain closed under the source policy", async () => {
	for (const uncertain of [false, true]) {
		const packet = await waterFixture(
			(x) => !uncertain && x >= 3,
			(x) => uncertain && x >= 3,
			{ xE7: 0, yE7: 0, stepE7: 25000, columns: 12, rows: 4 },
		);
		const g = grid();
		source(g);
		const policy = waterRoutingGeographyV6(shore(), packet.current);
		// The left quarters of cell1 are dry; cell2 samples are water or closed fallback.
		addPaidBoundaryCoverage(policy, g, 1000);
		assert.equal(bit(g.coverage, 2), 0);
	}
});

test("new or preexisting coverage never becomes a finite propagation source", () => {
	const g = grid(4);
	source(g);
	setBit(g.coverage, 2);
	const stats = addPaidBoundaryCoverage(geo(), g, 1000);
	assert.equal(stats.addedCells, 1);
	assert.equal(bit(g.coverage, 1), 1);
	assert.equal(bit(g.coverage, 3), 0);
	assert.deepEqual(Array.from(g.times), [20, 65535, 65535, 65535]);
});

test("neighbors do not wrap across raster rows", () => {
	const g = grid(3, 2);
	source(g, 2);
	for (const i of [0, 1, 4, 5]) setBit(g.coverage, i);
	assert.equal(addPaidBoundaryCoverage(geo(), g, 1000).addedCells, 0);
	assert.equal(bit(g.coverage, 3), 0);
});

test("open unreachable cells and existing road coverage are preserved", () => {
	const g = grid();
	source(g);
	setBit(g.land, 1);
	setBit(g.coverage, 2);
	const before = Array.from(g.coverage);
	assert.equal(addPaidBoundaryCoverage(geo(), g, 1000).addedCells, 0);
	assert.deepEqual(Array.from(g.coverage), before);
});

test("invalid horizon or finite closed center fails closed", () => {
	const g = grid();
	source(g);
	for (const n of [-1, 54001, Infinity, 0.5])
		assert.throws(() => addPaidBoundaryCoverage(geo(), g, n), /domain/);
	g.times[1] = 1;
	assert.throws(
		() => addPaidBoundaryCoverage(geo(), g, 1000),
		/Closed display center/,
	);
});

test("sealed renderer wrapper preserves point components and all noncoverage fields", () => {
	const p = contextDisplayFixture(
		[
			[0, 0.0025],
			[0.004, 0.0025],
		],
		[[0, 1, 100]],
	);
	const starts = [{ position: p.source.snap, initialTicks: 0 }];
	let oldGrid: unknown, newGrid: unknown, oldTime: unknown, newTime: unknown;
	let prepared: ReturnType<typeof prepareAccessPointTiming>[];
	const foot: [number, number] = [0.004, 0.0025];
	const target = {
		...p.source,
		origin: foot,
		snap: { ...p.source.snap, coordinate: foot, segmentFraction: 1 },
	};
	const targets = [
		{ point: foot, connection: target },
		{ point: [0.00625, 0.00125] as [number, number], connection: null },
	];
	const raw = Object.fromEntries(
		Object.entries(p.raw).map(([k, v]) => [k, v.slice()]),
	);
	const beforeSeed = (
		field: Parameters<typeof prepareAccessPointTiming>[2],
	) => {
		prepared = targets.map((t) =>
			prepareAccessPointTiming(
				p.graph,
				p.geometry,
				field,
				p.source.origin,
				t.point,
				t.connection,
			),
		);
	};
	const old = reusedContextDisplay(
		p.graph,
		p.geometry,
		p.contexts,
		shore(),
		p.source,
		starts,
		{
			maxTicks: 4800,
			beforeSeed,
			probe: (g) => {
				oldGrid = unchanged(g);
				oldTime = prepared.map((t) => finishAccessPointTiming(shore(), g, t));
			},
		},
		true,
	);
	const next = boundaryContextDisplay(
		p.graph,
		p.geometry,
		p.contexts,
		shore(),
		p.source,
		starts,
		{
			maxTicks: 4800,
			beforeSeed,
			probe: (g) => {
				newGrid = unchanged(g);
				newTime = prepared.map((t) => finishAccessPointTiming(shore(), g, t));
			},
		},
		true,
	);
	assert.deepEqual(newGrid, oldGrid);
	assert.deepEqual(newTime, oldTime);
	assert.ok(next.boundary.addedCells > 0);
	assert.equal(next.stats.localCells, old.stats.localCells);
	assert.equal(next.stats.roadOnlyCells, old.stats.roadOnlyCells);
	assert.equal(
		next.stats.selectedCells,
		old.stats.selectedCells + next.boundary.addedCells,
	);
	assert.equal(
		next.stats.maximumBackingBufferBytes,
		old.stats.maximumBackingBufferBytes,
	);
	for (const [k, value] of Object.entries(p.raw))
		assert.deepEqual(value, raw[k]);
});

test("success and held witness exceptions release all borrowed query backing", async () => {
	const p = contextDisplayFixture(
		[
			[0, 0.0025],
			[0.004, 0.0025],
		],
		[[0, 1, 100]],
	);
	const starts = [{ position: p.source.snap, initialTicks: 0 }];
	const baseline = await settledPhaseMemory();
	for (const fail of [false, true]) {
		const backing: WeakRef<ArrayBufferLike>[] = [];
		let held: Error | null = null;
		let loan: DisplayProbe | undefined;
		try {
			boundaryContextDisplay(
				p.graph,
				p.geometry,
				p.contexts,
				shore(),
				p.source,
				starts,
				{
					maxTicks: 4800,
					observeBacking: (buffers) =>
						backing.push(...buffers.map((b) => new WeakRef(b))),
					boundaryWitness: () => {
						if (fail) {
							held = new Error("held boundary witness");
							throw held;
						}
					},
					probe: (g) => {
						loan = g;
					},
				},
				true,
			);
			assert.ok(!fail);
		} catch (error) {
			assert.ok(fail);
			assert.equal(error, held);
		}
		if (loan)
			for (const v of Object.values(loan))
				if (ArrayBuffer.isView(v)) assert.equal(v.byteLength, 0);
		await settledPhaseMemory();
		assert.ok(
			(await settledPhaseMemory()).arrayBuffers <= baseline.arrayBuffers,
		);
		assert.ok(backing.every((b) => b.deref() === undefined));
	}
});
