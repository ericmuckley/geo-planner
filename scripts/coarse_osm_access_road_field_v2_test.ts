import assert from "node:assert/strict";
import test from "node:test";
import { setImmediate } from "node:timers/promises";
import { accessFilledDisplay } from "./coarse_osm_access_display_v1.ts";
import { geography, prepared } from "./coarse_osm_access_fixture_v2.ts";
import {
	type AccessStart,
	arrivalAtAccessPosition,
	computeAccessRoadField as original,
	computeDiagnosticAccessRoadField as originalDiagnostic,
} from "./coarse_osm_access_road_field_v1.ts";
import {
	computeAccessRoadField as revised,
	computeDiagnosticAccessRoadField as revisedDiagnostic,
} from "./coarse_osm_access_road_field_v2.ts";
import { BorrowedQueue } from "./coarse_osm_borrowed_queue_v1.ts";
import { MinQueue } from "./coarse_osm_min_queue_v1.ts";
import { connectorPrice } from "./coarse_osm_origin_connections_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import {
	fixture,
	type TestArc,
	words,
} from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import {
	arrivalAtRoadPosition,
	computeRoadField,
} from "./coarse_osm_road_field_v1.ts";

function setup(
	vertices: number,
	arcs: TestArc[],
	flags?: number[],
	pairs?: number[],
) {
	const graph = new PackedCarGraph(fixture(vertices, arcs, flags, pairs));
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((n) => [n, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	return { graph, geometry: new PaidRoadGeometry(graph, files) };
}
const start = (arc: number, fraction = 0, ticks = 0): AccessStart => ({
	position: { canonicalArc: arc, segment: 0, segmentFraction: fraction },
	initialTicks: ticks,
});
function equalFields(
	before: ReturnType<typeof original>,
	after: ReturnType<typeof revised>,
	saving: number,
) {
	assert.deepEqual(after.labels, before.labels);
	assert.deepEqual(after.vertexArrivalSeconds, before.vertexArrivalSeconds);
	assert.deepEqual(after.seeds, before.seeds);
	assert.deepEqual(after.source, before.source);
	assert.equal(after.horizonTicks, before.horizonTicks);
	assert.deepEqual(after.stats, {
		...before.stats,
		maximumBackingBufferBytes: before.stats.maximumBackingBufferBytes - saving,
	});
}

test("borrowed heap preserves all tied queue decisions and rejects overlapping views", () => {
	const buffer = new ArrayBuffer(8000),
		keys = new Uint32Array(buffer, 0, 1000),
		costs = new Uint32Array(buffer, 4000, 1000);
	const before = new MinQueue(1000),
		after = new BorrowedQueue(keys, costs);
	for (let i = 0; i < 1000; i++) {
		before.push(i, (i * 73) % 19);
		after.push(i, (i * 73) % 19);
	}
	assert.throws(() => after.push(0, 0), /heap limit/);
	while (before.length) assert.deepEqual(after.pop(), before.pop());
	assert.equal(after.peak, before.peak);
	assert.equal(after.keys.buffer, after.costs.buffer);
	assert.throws(() => after.pop(), /Empty/);
	assert.throws(() => new BorrowedQueue(keys, keys), /overlap/);
	assert.throws(() => new BorrowedQueue(keys, costs.subarray(1)), /capacity/);
	assert.throws(
		() => new BorrowedQueue(new Uint32Array(1000001), new Uint32Array(1000001)),
		/capacity/,
	);
});

test("both heap branches preserve turns, reversals, barriers, entry shadows and vertex seeds", () => {
	for (const vertices of [3, 128])
		for (const flags of [
			[4, 0, 6],
			[4, 1, 4],
			[4, 4, 4],
		]) {
			const p = setup(
				vertices,
				[
					[0, 1, 1000, 1],
					[1, 0, 1500, 0],
					[1, 2, 100],
					[2, 1, 100],
				],
				[...flags, ...Array(vertices - 3).fill(4)],
				[0, 2],
			);
			for (const horizon of [0, 250, 1500]) {
				const starts = [
						start(0, 0.25, 20),
						start(0, 0.75, 200),
						start(2, 0, 300),
					],
					options = { maxTicks: horizon, maxHeapEntries: 32 };
				equalFields(
					original(p.graph, p.geometry, starts, options),
					revised(p.graph, p.geometry, starts, options),
					vertices === 128 ? 256 : 0,
				);
			}
		}
});

test("generated borrowed and separate fields equal V1 and 9600 independent source minima", () => {
	let state = 20261103,
		comparisons = 0;
	const random = () => {
		state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
		return state / 2 ** 32;
	};
	for (let run = 0; run < 100; run++) {
		const vertices = run % 2 ? 128 : 8,
			arcs: TestArc[] = [];
		for (let tail = 0; tail < 8; tail++)
			for (let j = 0; j < 2; j++)
				arcs.push([
					tail,
					Math.floor(random() * 8),
					1 + Math.floor(random() * 500),
				]);
		const flags = Array.from({ length: vertices }, () => {
				const n = random();
				return n < 0.1 ? 1 : n < 0.3 ? 6 : 4;
			}),
			pairs: number[] = [];
		arcs.forEach((arc, i) => {
			const next = arcs.findIndex((a) => a[0] === arc[1]);
			if (next >= 0 && random() < 0.2) pairs.push(i, next);
		});
		const p = setup(vertices, arcs, flags, pairs),
			horizon = 100 + Math.floor(random() * 800),
			options = { maxTicks: horizon, maxHeapEntries: 32 };
		const starts = Array.from({ length: 5 }, () =>
			start(
				Math.floor(random() * arcs.length),
				[0, 0.25, 0.5, 0.75, 1][Math.floor(random() * 5)],
				Math.floor(random() * 100),
			),
		);
		const field = revised(p.graph, p.geometry, starts, options);
		equalFields(
			original(p.graph, p.geometry, starts, options),
			field,
			vertices === 128 ? 256 : 0,
		);
		const singles = starts.map((s) =>
			computeRoadField(
				p.graph,
				p.geometry,
				s.position,
				s.initialTicks,
				options,
			),
		);
		for (let arc = 0; arc < arcs.length; arc++)
			for (const fraction of [0, 0.1, 0.3, 0.5, 0.75, 1]) {
				const pos = start(arc, fraction).position;
				const finite = singles
					.map((f) => arrivalAtRoadPosition(p.graph, p.geometry, f, pos))
					.filter((v) => v !== null);
				assert.equal(
					arrivalAtAccessPosition(p.graph, p.geometry, field, pos),
					finite.length ? Math.min(...finite) : null,
				);
				comparisons++;
			}
	}
	assert.equal(comparisons, 9600);
});

test("restored borrowed fields produce byte-equal filled maps and preserve their arrays", () => {
	const p = prepared(
			Array.from({ length: 32 }, (_, i) => [i * 0.0003, 0] as const),
			[
				[0, 1],
				[1, 2],
			],
		),
		origin = [0, 0] as const;
	const starts = [start(0, 0, 0), start(1, 0.5, 20)],
		price = connectorPrice(origin, origin);
	const primary = {
		origin,
		snap: {
			...starts[0].position,
			coordinate: origin,
			distanceMeters: 0,
			forwardProgress: 0,
			backwardProgress: 0,
		},
		connectorTicks: price.ticks,
		connectorMeters: price.meters,
		kind: "modeled-road" as const,
	};
	for (const horizon of [400, 2400]) {
		const opts = { maxTicks: horizon, maxHeapEntries: 8 },
			before = original(p.graph, p.geometry, starts, opts),
			after = revised(p.graph, p.geometry, starts, opts);
		const labels = after.labels.slice(),
			vertices = after.vertexArrivalSeconds.slice(),
			options = { maxCells: 10000, heapEntries: 8 };
		assert.deepEqual(
			accessFilledDisplay(
				p.graph,
				p.geometry,
				geography(),
				primary,
				after,
				options,
			).output,
			accessFilledDisplay(
				p.graph,
				p.geometry,
				geography(),
				primary,
				before,
				options,
			).output,
		);
		assert.deepEqual(after.labels, labels);
		assert.deepEqual(after.vertexArrivalSeconds, vertices);
	}
});

test("limits, overflows and 900-minute diagnostics stay unchanged", () => {
	const p = setup(128, [
			[0, 1, 0xffffffff],
			[1, 2, 400000],
		]),
		starts = [start(0, 0, 10), start(0, 0.75, 500)];
	for (const maxTicks of [0, 300, 345600])
		equalFields(
			original(p.graph, p.geometry, starts, { maxTicks, maxHeapEntries: 32 }),
			revised(p.graph, p.geometry, starts, { maxTicks, maxHeapEntries: 32 }),
			256,
		);
	const opts = { maxTicks: 432000, maxHeapEntries: 32 };
	equalFields(
		originalDiagnostic(p.graph, p.geometry, [start(1)], opts),
		revisedDiagnostic(p.graph, p.geometry, [start(1)], opts),
		256,
	);
	for (const inputs of [[], Array(4097).fill(start(0)), [start(0, 0, -1)]])
		assert.throws(
			() => revised(p.graph, p.geometry, inputs),
			/source count|initial cost/,
		);
	assert.throws(() => revised(p.graph, p.geometry, starts, opts), /horizon/);
	const small = setup(128, [[0, 1, 10]]);
	assert.throws(
		() =>
			revised(small.graph, small.geometry, [start(0)], { maxHeapEntries: 0 }),
		/heap limit/,
	);
	assert.throws(
		() => revised(small.graph, small.geometry, [start(0)], { maxSettles: 0 }),
		/settle limit/,
	);
	assert.throws(
		() =>
			revised(p.graph, p.geometry, starts, {
				check: () => {
					throw new Error("cancelled");
				},
			}),
		/cancelled/,
	);
	const many = Array.from({ length: 4096 }, () => start(0, 0.5, 1));
	equalFields(
		original(p.graph, p.geometry, many, { maxHeapEntries: 32 }),
		revised(p.graph, p.geometry, many, { maxHeapEntries: 32 }),
		256,
	);
	assert.throws(
		() =>
			revised(
				{ ...p.graph, arcs: 16777215, vertices: 5731903 } as PackedCarGraph,
				p.geometry,
				starts,
			),
		/scratch/,
	);
});

test("country-sized sparse capacity fixture fits both the resolved and maximum pre-closure graph", () => {
	const p = setup(2, [[0, 1, 10]]),
		starts = Array.from({ length: 4096 }, () => start(0, 0, 1));
	for (const arcs of [9703850, 9837326]) {
		const graph = new Proxy(p.graph, {
			get(target, key) {
				if (key === "arcs") return arcs;
				if (key === "vertices") return 5731903;
				const value = Reflect.get(target, key);
				return typeof value === "function" ? value.bind(target) : value;
			},
		});
		const field = revised(graph, p.geometry, starts, { maxTicks: 0 });
		assert.equal(
			field.stats.maximumBackingBufferBytes,
			4 * arcs + 2 * 5731903 + 64 * 4096,
		);
		assert.ok(field.stats.maximumBackingBufferBytes < 67108864);
		assert.equal(field.stats.maximumHeapEntries, 0);
		assert.ok(field.labels.every((v) => v === 0xffffffff));
		assert.ok(field.vertexArrivalSeconds.every((v) => v === 65535));
		assert.equal(
			field.stats.returnedBackingBufferBytes,
			field.labels.buffer.byteLength +
				field.vertexArrivalSeconds.buffer.byteLength +
				field.seeds.buffer.byteLength,
		);
	}
});

test("repeated country-sized scratch releases below the unchanged one-MiB guard", async () => {
	assert.ok(global.gc, "Run with --expose-gc");
	const p = setup(2, [[0, 1, 10]]),
		starts = [start(0, 0, 1)];
	const graph = new Proxy(p.graph, {
		get(target, key) {
			if (key === "arcs") return 9703850;
			if (key === "vertices") return 5731903;
			const value = Reflect.get(target, key);
			return typeof value === "function" ? value.bind(target) : value;
		},
	});
	await setImmediate();
	global.gc();
	global.gc();
	const baseline = process.memoryUsage().arrayBuffers;
	function allocate() {
		const f = revised(graph, p.geometry, starts, { maxTicks: 0 });
		return [f.labels.buffer, f.vertexArrivalSeconds.buffer, f.seeds.buffer].map(
			(b) => new WeakRef(b),
		);
	}
	for (let i = 0; i < 12; i++) {
		const refs = allocate();
		await setImmediate();
		global.gc();
		global.gc();
		assert.ok(refs.every((r) => r.deref() === undefined));
		assert.ok(process.memoryUsage().arrayBuffers - baseline <= 1048576);
	}
});
