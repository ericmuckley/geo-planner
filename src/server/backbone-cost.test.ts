import assert from "node:assert/strict";
import { test } from "node:test";
import {
	type BaseRoadProof,
	baseRoadPrice,
	bufferedRoadVisits,
	replayCostAttachments,
	repriceRoadCosts,
	sourceRoadTimeFactor,
	validateRoadCosts,
} from "./backbone-cost";
import type { Backbone, BackboneGraph } from "./backbone-geometry";
import { pointTiming, searchBackbone } from "./backbone-routing";
import {
	distanceKm,
	type GridData,
	gridAttachments,
	type RoadVisit,
} from "./coarse-grid";

function fixture() {
	const roadKm = distanceKm([0.006, 0.0125], [0.044, 0.0125]);
	const graph: BackboneGraph = {
		nodeCoordinates: new Float64Array([0.006, 0.0125, 0.044, 0.0125]),
		arcFrom: new Uint32Array([0]),
		arcTo: new Uint32Array([1]),
		arcRoadKm: new Float64Array([roadKm]),
		arcMinutes: new Float64Array([(roadKm / 105) * 60 + 0.0005]),
		arcSpeedKph: new Uint8Array([105]),
		arcByteOffsets: new Uint32Array([0, 0]),
		arcInteriorOffsets: new Uint32Array([0, 0]),
		interiorSourceKm: new Float64Array(),
		geometryBytes: new Uint8Array(),
		partArcOffsets: new Uint32Array([0, 1]),
		crossingFirstArc: new Uint32Array(),
		endpointAdjOffsets: new Uint32Array([0, 1, 2]),
		endpointAdjArcs: new Uint32Array([0, 0]),
		cellIds: new Uint32Array([0, 1]),
		cellArcOffsets: new Uint32Array([0, 1, 2]),
		cellArcs: new Uint32Array([0, 0]),
	};
	const proof: BaseRoadProof = {
		key: 0,
		roadKm: 2,
		localKm: 0.3,
		speedKph: 85,
		connectorSpeedKph: 55,
		kind: "natural-earth",
		deciseconds: 0,
	};
	proof.deciseconds = baseRoadPrice(proof, 1);
	const visit: RoadVisit = {
		speedKph: 85,
		anchorIndex: 1,
		points: [
			[0.006, 0.0125],
			[0.0125, 0.0125],
			[0.019, 0.0125],
		],
		cumulativeKm: [
			0,
			distanceKm([0.006, 0.0125], [0.0125, 0.0125]),
			distanceKm([0.006, 0.0125], [0.019, 0.0125]),
		],
	};
	const base: GridData = {
		bounds: [0, 0, 0.05, 0.025],
		width: 2,
		height: 1,
		step: 0.025,
		localSpeedKph: 25,
		land: new Uint8Array([1, 1]),
		traversable: new Uint8Array([1, 1]),
		links: new Uint8Array(8),
		roadDeciseconds: new Uint16Array([proof.deciseconds, 0, 0, 0, 0, 0, 0, 0]),
		shoreLinks: new Uint8Array(2),
		boundary: [
			[
				[
					[-1, -1],
					[1, -1],
					[1, 1],
					[-1, 1],
					[-1, -1],
				],
			],
		],
		lakes: [],
		roadVisits: new Map([[0, visit]]),
	};
	const model: Backbone = { base, graph, originalNodes: 2 };
	return { model, proof, visit };
}

test("road allowance leaves connector/local pricing separate from the source term", () => {
	const p: BaseRoadProof = {
		key: 0,
		roadKm: 42.5,
		localKm: 12.5,
		speedKph: 85,
		connectorSpeedKph: 25,
		kind: "census",
		deciseconds: 36000,
	};
	assert.equal(baseRoadPrice(p, 1), 36000);
	assert.equal(baseRoadPrice(p, sourceRoadTimeFactor), 37800);
	assert.notEqual(
		baseRoadPrice(p, sourceRoadTimeFactor),
		Math.ceil(p.deciseconds * 1.1),
	);
	assert.throws(() => baseRoadPrice({ ...p, connectorSpeedKph: 55 }, 1.1));
	assert.throws(() => baseRoadPrice({ ...p, roadKm: 2000 }, 1.1));
});

test("control reproduces source rounding, every base link and retained visit count", () => {
	const { model, proof } = fixture();
	const result = validateRoadCosts(model, [proof]);
	assert.equal(result.sourceArcs, 1);
	assert.equal(result.baseLinks, 1);
	assert.equal(result.roadVisits, 1);
	assert.ok(Math.abs(result.maximumArcRounding - 0.0005) < 1e-12);
});

test("mutation changes only cost buffers and lazy road speed interpretation", () => {
	const { model, proof, visit } = fixture(),
		graph = model.graph;
	const original = graph.arcMinutes[0],
		rounding = original - (graph.arcRoadKm[0] / 105) * 60;
	const positions = graph.nodeCoordinates.slice(),
		mask = model.base.land.slice();
	const timeArray = graph.arcMinutes,
		baseTimes = model.base.roadDeciseconds;
	repriceRoadCosts(model, [proof]);
	assert.equal(graph.arcMinutes, timeArray);
	assert.equal(model.base.roadDeciseconds, baseTimes);
	assert.deepEqual(graph.nodeCoordinates, positions);
	assert.deepEqual(model.base.land, mask);
	assert.equal(graph.arcSpeedKph[0], 105);
	assert.equal(model.base.localSpeedKph, 25);
	assert.ok(
		Math.abs(
			graph.arcMinutes[0] - (graph.arcRoadKm[0] / 105) * 60 * 1.1 - rounding,
		) < 1e-12,
	);
	assert.equal(model.base.roadVisits?.get(0)?.speedKph, visit.speedKph / 1.1);
	assert.throws(() => repriceRoadCosts(model, [proof]), /already/);
});

test("wrong baseline costs, missing/duplicate proofs and bad rounding fail before mutation", () => {
	for (const kind of [
		"cost",
		"coverage",
		"duplicate",
		"rounding",
		"overflow",
	]) {
		const { model, proof } = fixture();
		let proofs = [proof];
		if (kind === "cost") proof.deciseconds++;
		if (kind === "coverage") proofs = [];
		if (kind === "duplicate") proofs = [proof, proof];
		if (kind === "rounding") model.graph.arcMinutes[0] += 0.01;
		if (kind === "overflow") {
			proof.roadKm = 1400;
		}
		const before = model.graph.arcMinutes.slice();
		assert.throws(() => repriceRoadCosts(model, proofs), RangeError, kind);
		assert.deepEqual(model.graph.arcMinutes, before);
	}
});

test("visit wrapper is no-cache and preserves anchor, geometry and local transfer", () => {
	const { model, visit } = fixture();
	visit.transferKm = 0.4;
	const visits = model.base.roadVisits;
	assert.ok(visits);
	assert.equal(bufferedRoadVisits(visits, 1), visits);
	const wrapped = bufferedRoadVisits(visits);
	assert.ok(wrapped);
	assert.equal(wrapped.size, visits.size);
	assert.equal(wrapped.get(9), undefined);
	const a = wrapped.get(0),
		b = wrapped.get(0);
	assert.ok(a && b);
	assert.notEqual(a, b);
	assert.equal(a.points, visit.points);
	assert.equal(a.cumulativeKm, visit.cumulativeKm);
	assert.equal(a.anchorIndex, visit.anchorIndex);
	assert.equal(a.transferKm, 0.4);
	assert.equal([...wrapped][0][1].speedKph, 85 / 1.1);
});

test("NE partial access charges buffered road distance and unchanged local access", () => {
	const { model, proof } = fixture(),
		origin = { lon: 0.007, lat: 0.013 };
	const projected = [origin.lon, 0.0125],
		anchor = [0.0125, 0.0125];
	const local = (distanceKm([origin.lon, origin.lat], projected) / 25) * 60;
	const road = (distanceKm(projected, anchor) / 85) * 60;
	const round = (v: number) => Math.ceil(v * 600) / 600;
	assert.equal(
		gridAttachments(model.base, origin)[0].minutes,
		round(local + road),
	);
	repriceRoadCosts(model, [proof]);
	assert.equal(
		gridAttachments(model.base, origin)[0].minutes,
		round(local + road * 1.1),
	);
});

test("independent attachment replay matches frozen core before and after allowance", () => {
	for (const water of [false, true]) {
		const { model, proof } = fixture();
		if (water)
			model.base.lakes = [
				[
					[
						[0.021, -0.01],
						[0.023, -0.01],
						[0.023, 0.03],
						[0.021, 0.03],
						[0.021, -0.01],
					],
				],
			];
		for (const origin of [
			{ lon: 0.01, lat: 0.0125 },
			{ lon: 0.049, lat: 0.02 },
		])
			assert.deepEqual(
				replayCostAttachments(model, origin),
				searchBackbone(model, origin, 0).input,
			);
		repriceRoadCosts(model, [proof]);
		for (const origin of [
			{ lon: 0.01, lat: 0.0125 },
			{ lon: 0.049, lat: 0.02 },
		])
			assert.deepEqual(
				replayCostAttachments(model, origin),
				searchBackbone(model, origin, 0).input,
			);
	}
});

test("same-arc partial timing uses new source terms and preserves local/rounding semantics", () => {
	const { model, proof } = fixture();
	model.base.roadVisits = undefined;
	model.base.traversable.fill(0);
	const origin = { lon: 0.015, lat: 0.0125 },
		destination = { lon: 0.035, lat: 0.0125 };
	const before = pointTiming(
		model,
		searchBackbone(model, origin, 10),
		destination,
	);
	assert.ok(before?.direct);
	repriceRoadCosts(model, [proof]);
	const after = pointTiming(
		model,
		searchBackbone(model, origin, 10),
		destination,
	);
	assert.ok(after?.direct);
	const fraction = (destination.lon - origin.lon) / (0.044 - 0.006);
	const expected = Math.ceil(model.graph.arcMinutes[0] * fraction * 600) / 600;
	assert.ok(Math.abs(after.minutes - expected) < 1e-8);
	assert.ok(after.minutes > before.minutes);
});
