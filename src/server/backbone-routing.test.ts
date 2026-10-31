import assert from "node:assert/strict";
import { test } from "node:test";
import {
	type Backbone,
	type BackboneGraph,
	nodeArcs,
	type Point,
	pointCell,
	pointCells,
	sourceMinutes,
	sourceSegments,
} from "./backbone-geometry";
import {
	backboneContour,
	backboneTransitions,
	pointTiming,
	searchBackbone,
	transferMinutes,
} from "./backbone-routing";
import { distanceKm, type GridData } from "./coarse-grid";

type Arc = { from: number; to: number; minutes?: number; interiors?: Point[] };
const polygon = (west: number, south: number, east: number, north: number) => [
	[
		[west, south],
		[east, south],
		[east, north],
		[west, north],
		[west, south],
	],
];
function fixture(
	points: Point[],
	arcs: Arc[],
	width = 3,
	height = 1,
): Backbone {
	const cells = width * height;
	const base: GridData = {
		bounds: [0, 0, width, height],
		width,
		height,
		step: 1,
		localSpeedKph: 25,
		land: new Uint8Array(cells).fill(1),
		traversable: new Uint8Array(cells).fill(1),
		displayLand: new Uint8Array(cells).fill(1),
		links: new Uint8Array(cells * 4),
		shoreLinks: new Uint8Array(cells),
		boundary: [polygon(-1, -1, width + 1, height + 1)],
		lakes: [],
	};
	const bytes: number[] = [],
		byteOffsets = [0],
		interiorOffsets = [0],
		interiorKm: number[] = [],
		roadKm: number[] = [];
	const memberships = Array.from({ length: cells }, () => new Set<number>());
	const adjacent = points.map(() => [] as number[]);
	const signed = (delta: number) => {
		let value = delta < 0 ? -delta * 2 - 1 : delta * 2;
		do {
			const byte = value % 128;
			value = Math.floor(value / 128);
			bytes.push(byte + (value ? 128 : 0));
		} while (value);
	};
	for (const [index, arc] of arcs.entries()) {
		const path = [points[arc.from], ...(arc.interiors ?? []), points[arc.to]];
		let km = 0,
			x = Math.round(path[0][0] * 100000),
			y = Math.round(path[0][1] * 100000);
		for (let i = 1; i < path.length; i++) {
			km += distanceKm(path[i - 1], path[i]);
			if (i < path.length - 1) {
				const xx = Math.round(path[i][0] * 100000),
					yy = Math.round(path[i][1] * 100000);
				signed(xx - x);
				signed(yy - y);
				x = xx;
				y = yy;
				interiorKm.push(km);
			}
			for (const point of [
				path[i - 1],
				path[i],
				[(path[i - 1][0] + path[i][0]) / 2, (path[i - 1][1] + path[i][1]) / 2],
			]) {
				const cell = pointCell(base, point);
				if (cell >= 0) memberships[cell].add(index);
			}
		}
		roadKm.push(km);
		byteOffsets.push(bytes.length);
		interiorOffsets.push(interiorKm.length);
		adjacent[arc.from].push(index);
		adjacent[arc.to].push(index);
	}
	const ids: number[] = [],
		cellOffsets = [0],
		cellValues: number[] = [],
		nodeOffsets = [0],
		nodeValues: number[] = [];
	for (const [id, values] of memberships.entries())
		if (values.size) {
			ids.push(id);
			cellValues.push(...values);
			cellOffsets.push(cellValues.length);
		}
	for (const values of adjacent) {
		nodeValues.push(...values);
		nodeOffsets.push(nodeValues.length);
	}
	const graph: BackboneGraph = {
		nodeCoordinates: Float64Array.from(points.flat()),
		arcFrom: Uint32Array.from(arcs.map((a) => a.from)),
		arcTo: Uint32Array.from(arcs.map((a) => a.to)),
		arcRoadKm: Float64Array.from(roadKm),
		arcMinutes: Float64Array.from(
			arcs.map((a, i) => a.minutes ?? (roadKm[i] / 85) * 60),
		),
		arcSpeedKph: new Uint8Array(arcs.length).fill(85),
		arcByteOffsets: Uint32Array.from(byteOffsets),
		arcInteriorOffsets: Uint32Array.from(interiorOffsets),
		interiorSourceKm: Float64Array.from(interiorKm),
		geometryBytes: Uint8Array.from(bytes),
		partArcOffsets: Uint32Array.from([0, arcs.length]),
		crossingFirstArc: new Uint32Array(),
		endpointAdjOffsets: Uint32Array.from(nodeOffsets),
		endpointAdjArcs: Uint32Array.from(nodeValues),
		cellIds: Uint32Array.from(ids),
		cellArcOffsets: Uint32Array.from(cellOffsets),
		cellArcs: Uint32Array.from(cellValues),
	};
	return { base, graph, originalNodes: points.length };
}

test("streaming source geometry preserves negative deltas, bends and stored cumulative costs", () => {
	const model = fixture(
		[
			[0.2, 0.2],
			[0.8, 0.2],
		],
		[
			{
				from: 0,
				to: 1,
				interiors: [
					[0.5, 0.4],
					[0.4, 0.3],
				],
				minutes: 120,
			},
		],
	);
	const segments = [...sourceSegments(model.graph, 0)];
	assert.deepEqual(
		segments.map((s) => s.b),
		[
			[0.5, 0.4],
			[0.4, 0.3],
			[0.8, 0.2],
		],
	);
	assert.equal(segments[2].endKm, model.graph.arcRoadKm[0]);
	const km = segments[0].endKm;
	assert.ok(
		sourceMinutes(model.graph, 0, km, segments[0].a, segments[0].b) >=
			(120 * km) / model.graph.arcRoadKm[0],
	);
	assert.ok(model.graph.arcRoadKm[0] > distanceKm([0.2, 0.2], [0.8, 0.2]));
});

test("geometry rejects overflow, noncanonical, truncated and extra coordinates", () => {
	for (const bytes of [[128], [128, 0, 0], [255, 255, 255, 255, 16, 0], [0]]) {
		const model = fixture(
			[
				[0.2, 0.2],
				[0.8, 0.2],
			],
			[{ from: 0, to: 1, interiors: [[0.4, 0.3]] }],
		);
		model.graph.geometryBytes = Uint8Array.from(bytes);
		model.graph.arcByteOffsets[1] = bytes.length;
		assert.throws(() => [...sourceSegments(model.graph, 0)], RangeError);
	}
});

test("ties-to-even seeds match Python for positive and negative halves", () => {
	for (const sign of [1, -1]) {
		const model = fixture(
			[
				[sign * 0.000005, 0],
				[0.1, 0],
			],
			[{ from: 0, to: 1, interiors: [[0, 0]] }],
		);
		model.graph.geometryBytes = Uint8Array.from([0, 0]);
		model.graph.arcByteOffsets[1] = 2;
		const first = [...sourceSegments(model.graph, 0)][0];
		assert.deepEqual(first.b, [0, 0]);
	}
});

test("junction CSR and crossing incidence preserve separate coincident road identities", () => {
	const model = fixture(
		[
			[0.2, 0.3],
			[0.8, 0.3],
			[0.5, 0.3],
			[0.2, 0.3],
			[0.8, 0.3],
		],
		[
			{ from: 0, to: 2 },
			{ from: 2, to: 1 },
			{ from: 3, to: 4 },
		],
	);
	model.originalNodes = 2;
	model.graph.crossingFirstArc = Uint32Array.from([0]);
	assert.deepEqual([...nodeArcs(model, 2)], [0, 1]);
	const road = [...backboneTransitions(model, 3 + 2)].filter(
		(e) => e.kind === "road",
	);
	assert.deepEqual(
		road.map((e) => e.target),
		[3, 4],
	);
	assert.ok(
		road.every((e) => e.minutes === model.graph.arcMinutes[e.arc ?? -1]),
	);
});

test("closed-cell boundary transfers are symmetric, including upper/right indexed endpoints", () => {
	const model = fixture(
		[
			[1, 0.5],
			[1.8, 0.5],
		],
		[{ from: 0, to: 1 }],
		2,
	);
	assert.deepEqual(pointCells(model.base, [1, 0.5]), [0, 1]);
	for (const cell of [0, 1]) {
		const out = [...backboneTransitions(model, cell)].find(
			(e) => e.target === 2,
		);
		const back = [...backboneTransitions(model, 2)].find(
			(e) => e.target === cell,
		);
		assert.ok(out && back);
		assert.equal(out.minutes, back.minutes);
		assert.ok(
			out.minutes >= (distanceKm([cell + 0.5, 0.5], [1, 0.5]) / 25) * 60,
		);
	}
});

test("coincident cross-layer transfers remain positive and paid", () => {
	const model = fixture(
		[
			[0.5, 0.5],
			[0.8, 0.5],
		],
		[{ from: 0, to: 1 }],
		1,
	);
	assert.equal(transferMinutes(model, 0, 0), 1 / 600);
});

test("strict local transfers cannot cross a lake or an island channel", () => {
	const model = fixture(
		[
			[0.9, 0.5],
			[0.95, 0.5],
		],
		[{ from: 0, to: 1 }],
		1,
	);
	model.base.lakes = [polygon(0.6, 0.1, 0.7, 0.9)];
	assert.equal(transferMinutes(model, 0, 0), Infinity);
	model.base.lakes = [];
	model.base.boundary = [polygon(0, 0, 0.6, 1), polygon(0.7, 0, 1, 1)];
	assert.equal(transferMinutes(model, 0, 0), Infinity);
});

test("direct same-arc attachment avoids endpoint detours and pays interpolated source costs", () => {
	const model = fixture(
		[
			[0.2, 0.2],
			[0.8, 0.2],
		],
		[{ from: 0, to: 1, minutes: 100 }],
		1,
	);
	model.base.traversable.fill(0);
	const field = searchBackbone(model, { lon: 0.4, lat: 0.2 }, 200);
	const measured = pointTiming(model, field, { lon: 0.6, lat: 0.2 });
	assert.ok(measured?.direct);
	assert.ok(Math.abs(measured.minutes - 100 / 3) < 1 / 600 + 1e-8);
	assert.ok(
		measured.components.road >= (distanceKm([0.4, 0.2], [0.6, 0.2]) / 85) * 60,
	);
});

test("partial source cost has a physical chord lower bound even at zero cumulative difference", () => {
	const model = fixture(
		[
			[0.2, 0.2],
			[0.8, 0.2],
		],
		[{ from: 0, to: 1 }],
		1,
	);
	assert.equal(
		sourceMinutes(model.graph, 0, 0, [0.2, 0.2], [0.3, 0.2]),
		(distanceKm([0.2, 0.2], [0.3, 0.2]) / 85) * 60,
	);
});

test("an explicit source bridge can traverse water while local access cannot", () => {
	const model = fixture(
		[
			[0.2, 0.5],
			[2.8, 0.5],
		],
		[{ from: 0, to: 1 }],
	);
	model.base.traversable.fill(0);
	model.base.lakes = [polygon(1, 0, 2, 1)];
	const field = searchBackbone(model, { lon: 0.2, lat: 0.5 }, 500);
	assert.equal(field.labels[4], model.graph.arcMinutes[0]);
});

test("display arrival respects partial arc progress and does not shade a distant endpoint cell early", () => {
	const model = fixture(
		[
			[0.2, 0.5],
			[2.8, 0.5],
			[1, 0.5],
			[2, 0.5],
		],
		[
			{ from: 0, to: 2, minutes: 100 },
			{ from: 2, to: 3, minutes: 100 },
			{ from: 3, to: 1, minutes: 100 },
		],
	);
	model.base.traversable.fill(0);
	model.originalNodes = 2;
	model.graph.crossingFirstArc = Uint32Array.from([0, 1]);
	const field = searchBackbone(model, { lon: 0.2, lat: 0.5 }, 500);
	assert.deepEqual([...backboneContour(model, field, 50).mask], [1, 0, 0]);
	assert.deepEqual([...backboneContour(model, field, 150).mask], [1, 1, 0]);
	assert.deepEqual([...backboneContour(model, field, 250).mask], [1, 1, 1]);
});

test("arbitrary-origin search matches independent Bellman-Ford relaxation and reconstructs physical edges", () => {
	const model = fixture(
		[
			[0.2, 0.3],
			[1, 0.3],
			[1.8, 0.7],
			[2.8, 0.6],
		],
		[
			{ from: 0, to: 1 },
			{ from: 1, to: 2 },
			{ from: 2, to: 3 },
			{ from: 0, to: 2, interiors: [[0.7, 0.6]] },
		],
	);
	const original = model.base.land.slice(),
		origin = { lon: 0.23, lat: 0.47 };
	const field = searchBackbone(model, origin, 900),
		reference = new Float64Array(field.labels.length).fill(Infinity);
	for (const seed of field.input.seeds) reference[seed.node] = seed.minutes;
	for (let iteration = 0; iteration < reference.length; iteration++)
		for (let node = 0; node < reference.length; node++)
			for (const edge of backboneTransitions(model, node))
				if (reference[node] + edge.minutes <= 900)
					reference[edge.target] = Math.min(
						reference[edge.target],
						reference[node] + edge.minutes,
					);
	for (let i = 0; i < reference.length; i++)
		assert.ok(
			Math.abs(reference[i] - field.labels[i]) < 1e-8 ||
				reference[i] === field.labels[i],
		);
	const timing = pointTiming(model, field, { lon: 2.71, lat: 0.62 });
	assert.ok(timing);
	assert.ok(
		Math.abs(
			Object.values(timing.components).reduce((a, b) => a + b, 0) -
				timing.minutes,
		) < 1e-8,
	);
	assert.ok(timing.edges.every((e) => e.minutes > 0));
	assert.deepEqual(model.base.land, original);
	const repeated = searchBackbone(model, origin, 900);
	assert.deepEqual(field.labels, repeated.labels);
});

test("invalid inputs are rejected and unsupported accepted origins remain isolated without mask mutation", () => {
	const model = fixture([], [], 2);
	model.base.traversable.fill(0);
	assert.throws(
		() => searchBackbone(model, { lon: NaN, lat: 0.5 }, 120),
		RangeError,
	);
	assert.throws(
		() => searchBackbone(model, { lon: 3, lat: 0.5 }, 120),
		RangeError,
	);
	assert.throws(
		() => searchBackbone(model, { lon: 0.5, lat: 0.5 }, -1),
		RangeError,
	);
	model.base.lakes = [polygon(0.2, 0.1, 1.8, 0.9)];
	assert.throws(
		() => searchBackbone(model, { lon: 0.5, lat: 0.5 }, 120),
		RangeError,
	);
	model.base.lakes = [];
	const field = searchBackbone(model, { lon: 0.3, lat: 0.6 }, 120);
	assert.deepEqual([...backboneContour(model, field, 120).mask], [1, 0]);
	assert.equal(pointTiming(model, field, { lon: 1.5, lat: 0.5 }), null);
	assert.deepEqual([...model.base.traversable], [0, 0]);
	assert.throws(() => backboneContour(model, field, 121), RangeError);
});
