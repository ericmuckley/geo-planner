import assert from "node:assert/strict";
import test from "node:test";
import { prepared } from "./coarse_osm_access_fixture_v2.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { terminalRoadPhase } from "./coarse_osm_terminal_phase_v3.ts";

function inputs() {
	const p = prepared(
		[
			[0, 0],
			[0.001, 0],
		],
		[[0, 1]],
	);
	const connection = (fraction: number): OriginConnection => ({
		origin: [0, 0],
		connectorTicks: 0,
		connectorMeters: 0,
		kind: "modeled-road",
		snap: {
			canonicalArc: 0,
			segment: 0,
			segmentFraction: fraction,
			coordinate: [0, 0],
			distanceMeters: 0,
			forwardProgress: fraction,
			backwardProgress: 1 - fraction,
		},
	});
	const starts = [
		{
			position: { canonicalArc: 0, segment: 0, segmentFraction: 0.25 },
			initialTicks: 23,
		},
	];
	return { ...p, connection, starts };
}

test("terminal phase keeps only scalar results after repeated country-sized fields", async () => {
	const p = inputs();
	Object.defineProperty(p.graph, "arcs", { value: 9744462 });
	Object.defineProperty(p.graph, "vertices", { value: 5731903 });
	Object.defineProperty(p.graph, "arcTail", {
		value: (arc: number) => {
			assert.equal(arc, 0);
			return 0;
		},
	});
	const before = await settledPhaseMemory(),
		summaries = [];
	for (let i = 0; i < 32; i++) {
		const result = terminalRoadPhase(p.graph, p.geometry, p.starts, [
			{
				primary: p.connection(0.75),
				alternatives: [p.connection(0.75), p.connection(0.5)],
			},
		]);
		assert.equal(result.finishes[0].primary?.ticks, 523);
		assert.deepEqual(result.finishes[0].best, { ticks: 273, index: 1 });
		summaries.push(result);
		await assertPhaseReleased(
			before.arrayBuffers,
			"repeated terminal phase release",
		);
	}
	assert.equal(summaries.length, 32);
});

test("terminal phase releases its country field when a terminal-price check throws", async () => {
	const p = inputs();
	Object.defineProperty(p.graph, "arcs", { value: 9744462 });
	Object.defineProperty(p.graph, "vertices", { value: 5731903 });
	Object.defineProperty(p.graph, "arcTail", {
		value: (arc: number) => {
			assert.equal(arc, 0);
			return 0;
		},
	});
	const before = await settledPhaseMemory();
	for (let i = 0; i < 8; i++) {
		const bad = { ...p.connection(0.5), connectorTicks: 1 };
		assert.throws(
			() =>
				terminalRoadPhase(p.graph, p.geometry, p.starts, [
					{ primary: bad, alternatives: [bad] },
				]),
			/Unpaid/,
		);
		await assertPhaseReleased(
			before.arrayBuffers,
			"failed terminal phase release",
		);
	}
});

test("scoped field labels, vertex minima and source states match the sealed implementation", async () => {
	const { computeDiagnosticAccessRoadField } = await import(
		"./coarse_osm_access_road_field_v2.ts"
	);
	const { withDiagnosticAccessRoadField } = await import(
		"./coarse_osm_scoped_access_field_v3.ts"
	);
	const p = prepared(
		[
			[0, 0],
			[0.001, 0],
			[0.001, 0.001],
		],
		[
			[0, 1],
			[1, 2],
			[2, 0],
		],
	);
	for (let i = 0; i < 32; i++) {
		const starts = [
			{
				position: { canonicalArc: 0, segment: 0, segmentFraction: i / 32 },
				initialTicks: 23,
			},
			{
				position: {
					canonicalArc: 1,
					segment: 0,
					segmentFraction: (31 - i) / 32,
				},
				initialTicks: 100,
			},
		];
		const expected = computeDiagnosticAccessRoadField(
			p.graph,
			p.geometry,
			starts,
			{ maxTicks: 1800, maxHeapEntries: 256 },
		);
		const actual = withDiagnosticAccessRoadField(
			p.graph,
			p.geometry,
			starts,
			(field) => ({
				labels: Uint32Array.from(field.labels),
				vertices: Uint16Array.from(field.vertexArrivalSeconds),
				source: { ...field.source },
				stats: { ...field.stats },
			}),
			{ maxTicks: 1800, maxHeapEntries: 256 },
		);
		assert.deepEqual(actual, {
			labels: expected.labels,
			vertices: expected.vertexArrivalSeconds,
			source: expected.source,
			stats: expected.stats,
		});
	}
});
