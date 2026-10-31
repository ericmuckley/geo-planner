import assert from "node:assert/strict";
import { test } from "node:test";
import {
	type Backbone,
	type BackboneGraph,
	nodePoint,
} from "./backbone-geometry";
import {
	type CapturedPath,
	controlledCostChange,
	priceCapturedPath,
	sameStateSequence,
} from "./backbone-path-control";
import { backboneTransitions } from "./backbone-routing";
import { type GridData, gridPosition } from "./coarse-grid";

function fixture(): Backbone {
	const base: GridData = {
		bounds: [0, 0, 3, 1],
		width: 3,
		height: 1,
		step: 1,
		localSpeedKph: 25,
		land: new Uint8Array([1, 1, 1]),
		traversable: new Uint8Array(3),
		links: new Uint8Array(12),
		roadDeciseconds: new Uint16Array(12),
		shoreLinks: new Uint8Array(3),
		boundary: [
			[
				[
					[-1, -1],
					[4, -1],
					[4, 2],
					[-1, 2],
					[-1, -1],
				],
			],
		],
		lakes: [],
	};
	const graph: BackboneGraph = {
		nodeCoordinates: new Float64Array([0.2, 0.5, 1.2, 0.5, 2.2, 0.5]),
		arcFrom: new Uint32Array([0, 1]),
		arcTo: new Uint32Array([1, 2]),
		arcRoadKm: new Float64Array([112, 112]),
		arcMinutes: new Float64Array([75, 75]),
		arcSpeedKph: new Uint8Array([105, 105]),
		arcByteOffsets: new Uint32Array([0, 0, 0]),
		arcInteriorOffsets: new Uint32Array([0, 0, 0]),
		interiorSourceKm: new Float64Array(),
		geometryBytes: new Uint8Array(),
		partArcOffsets: new Uint32Array([0, 2]),
		crossingFirstArc: new Uint32Array(),
		endpointAdjOffsets: new Uint32Array([0, 1, 3, 4]),
		endpointAdjArcs: new Uint32Array([0, 0, 1, 1]),
		cellIds: new Uint32Array([0, 1, 2]),
		cellArcOffsets: new Uint32Array([0, 1, 3, 4]),
		cellArcs: new Uint32Array([0, 0, 1, 1]),
	};
	return { base, graph, originalNodes: 3 };
}

function capture(
	model: Backbone,
	states: number[],
	arcs?: number[],
): CapturedPath {
	const position = (node: number) =>
		node < model.base.width * model.base.height
			? gridPosition(model.base, node)
			: nodePoint(model.graph, node - model.base.width * model.base.height);
	const edges = states.slice(1).map((target, i) => {
		const edge = [...backboneTransitions(model, states[i])].find(
			(e) => e.target === target && (!arcs || e.arc === arcs[i]),
		);
		assert.ok(edge);
		return {
			...edge,
			fromPoint: position(states[i]),
			toPoint: position(target),
		};
	});
	const components = {
		origin: 0,
		road: 0,
		local: 0,
		transfer: 0,
		destination: 0,
	};
	for (const edge of edges) components[edge.kind] += edge.minutes;
	const a = position(states[0]),
		b = position(states.at(-1) ?? -1);
	return {
		id: "synthetic",
		origin: { lon: a[0], lat: a[1] },
		destination: { lon: b[0], lat: b[1] },
		pointMinutes: Object.values(components).reduce((a, b) => a + b, 0),
		components,
		direct: null,
		edges,
	};
}

test("held source-state sequence reproduces old costs and computes new prefixes without search", () => {
	const model = fixture(),
		path = capture(model, [3, 4, 5]);
	const before = priceCapturedPath(model, path, true);
	assert.equal(before.minutes, 150);
	model.graph.arcMinutes.set([82.5, 82.5]);
	const held = priceCapturedPath(model, path);
	assert.equal(held.minutes, 165);
	assert.equal(held.maximumStateMinutes, 165);
	const effect = controlledCostChange(
		before.minutes,
		held.minutes,
		160,
		held.maximumStateMinutes,
		900,
	);
	assert.equal(effect.directCostShift, 15);
	assert.equal(effect.pathChoiceBenefit, 5);
	assert.equal(effect.actualCostShift, 10);
});

test("parallel source arc identity is held even when another arc has the same endpoints", () => {
	const model = fixture();
	model.originalNodes = 2;
	model.graph.nodeCoordinates = model.graph.nodeCoordinates.slice(0, 4);
	model.graph.arcFrom.set([0, 0]);
	model.graph.arcTo.set([1, 1]);
	model.graph.arcMinutes.set([75, 95]);
	model.graph.endpointAdjOffsets = new Uint32Array([0, 2, 4]);
	model.graph.endpointAdjArcs = new Uint32Array([0, 1, 0, 1]);
	const path = capture(model, [3, 4], [1]);
	assert.equal(priceCapturedPath(model, path, true).minutes, 95);
	model.graph.endpointAdjArcs = new Uint32Array([0, 0, 0, 0]);
	assert.throws(() => priceCapturedPath(model, path), /no longer eligible/);
});

test("base road can become local within a held state pair and is reported separately", () => {
	const model = fixture();
	model.base = {
		...model.base,
		bounds: [0, 0, 0.05, 0.025],
		width: 2,
		height: 1,
		step: 0.025,
		land: new Uint8Array([1, 1]),
		traversable: new Uint8Array([1, 1]),
		links: new Uint8Array(8),
		roadDeciseconds: new Uint16Array([3900, 0, 0, 0, 0, 0, 0, 0]),
		shoreLinks: new Uint8Array(2),
	};
	model.graph.nodeCoordinates = new Float64Array();
	model.graph.cellIds = new Uint32Array();
	model.originalNodes = 0;
	const path = capture(model, [0, 1]);
	assert.equal(path.pointMinutes, 6.5);
	const times = model.base.roadDeciseconds;
	assert.ok(times);
	times[0] = 4290;
	const held = priceCapturedPath(model, path);
	assert.equal(held.kindChanges, 1);
	assert.equal(held.components.road, 0);
	assert.ok(held.components.local > 6.5 && held.components.local < 7.15);
});

test("bound applicability uses graph prefixes and excludes the final point attachment", () => {
	const value = controlledCostChange(150, 195, 190, 165, 180);
	assert.equal(value.boundApplied, true);
	assert.equal(value.pathChoiceBenefit, 5);
	assert.equal(controlledCostChange(150, 165, 190, 165, 150).capLimited, true);
});

test("worse actual cost under an eligible held path fails while cap-limited gaps stay visible", () => {
	assert.throws(() => controlledCostChange(150, 165, 166, 165, 900), /exceeds/);
	const limited = controlledCostChange(150, 165, 166, 165, 160);
	assert.equal(limited.boundApplied, false);
	assert.equal(limited.pathChoiceBenefit, -1);
	assert.throws(
		() => controlledCostChange(150, 149, 149, 149, 900),
		/decreased/,
	);
});

test("discontinuous chains, moved coordinates and stale recorded prices are rejected", () => {
	for (const kind of ["chain", "position", "price"]) {
		const model = fixture(),
			path = capture(model, [3, 4, 5]);
		if (kind === "chain") path.edges[1].from = 3;
		if (kind === "position") path.edges[0].fromPoint = [0.201, 0.5];
		if (kind === "price") path.edges[0].minutes++;
		assert.throws(() => priceCapturedPath(model, path, true), Error, kind);
	}
});

test("state/arc identity comparison ignores road/local kind changes", () => {
	const model = fixture(),
		a = capture(model, [3, 4, 5]),
		b = structuredClone(a);
	b.edges[0].kind = "local";
	assert.equal(sameStateSequence(a, b), true);
	b.edges[0].arc = 9;
	assert.equal(sameStateSequence(a, b), false);
});

test("accounting leaves shared arrays unchanged and unsupported records fail explicitly", () => {
	const model = fixture(),
		path = capture(model, [3, 4, 5]);
	const costs = model.graph.arcMinutes.slice(),
		mask = model.base.land.slice();
	priceCapturedPath(model, path, true);
	priceCapturedPath(model, path);
	assert.deepEqual(model.graph.arcMinutes, costs);
	assert.deepEqual(model.base.land, mask);
	assert.throws(() => priceCapturedPath(model, { ...path, edges: [] }));
	assert.throws(() =>
		priceCapturedPath(model, { ...path, direct: { arc: 0 } }),
	);
	assert.throws(() => controlledCostChange(NaN, 1, 1, 1, 900));
});
