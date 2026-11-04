import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { diagnosticFilledDisplay } from "./coarse_osm_diagnostic_display_v1.ts";
import { computeDiagnosticRoadField } from "./coarse_osm_diagnostic_field_v1.ts";
import { displayPointTiming } from "./coarse_osm_display_timing_v1.ts";
import { filledDisplay } from "./coarse_osm_filled_display_v1.ts";
import type {
	OriginConnection,
	OriginGeography,
} from "./coarse_osm_origin_connections_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import { computeRoadField } from "./coarse_osm_road_field_v1.ts";

function example() {
	const files = fixture(2, [[0, 1, 400000]]);
	files["routing/xy.i32"] = words([0, 0, 1000000, 0], 4, true);
	const graph = new PackedCarGraph(files),
		shapes = Object.fromEntries(
			PAID_GEOMETRY_FILES.map((n) => [n, new Uint8Array()]),
		) as PaidGeometryFiles;
	shapes["geometry/curve-offsets.u32"] = words([0], 4);
	const geometry = new PaidRoadGeometry(graph, shapes),
		snap = {
			canonicalArc: 0,
			segment: 0,
			segmentFraction: 0,
			coordinate: [0, 0] as const,
			distanceMeters: 0,
			forwardProgress: 0,
			backwardProgress: 0,
		};
	const source: OriginConnection = {
		origin: [0, 0],
		snap,
		connectorTicks: 0,
		connectorMeters: 0,
		kind: "modeled-road",
	};
	const geography: OriginGeography = {
		bounds: [-0.2, -0.2, 0.2, 0.2],
		boundary: [
			[
				[
					[-0.2, -0.2],
					[0.2, -0.2],
					[0.2, 0.2],
					[-0.2, 0.2],
					[-0.2, -0.2],
				],
			],
		],
		lakes: [],
	};
	return { graph, geometry, source, geography };
}
test("diagnostic copies differ from frozen algorithms only in named entry points/ceilings", () => {
	const road = readFileSync(
		new URL("./coarse_osm_road_field_v1.ts", import.meta.url),
		"utf8",
	)
		.replace(/\/\*\*.*?\*\//s, "")
		.replace(
			"export function computeRoadField(",
			"export function computeDiagnosticRoadField(",
		)
		.replace(
			"options.maxTicks ?? TWELVE_HOURS_TICKS",
			"options.maxTicks ?? 432000",
		)
		.replace(
			'integer(horizonTicks, TWELVE_HOURS_TICKS, "horizon");',
			'integer(horizonTicks, 432000, "horizon");',
		);
	assert.equal(
		readFileSync(
			new URL("./coarse_osm_diagnostic_field_v1.ts", import.meta.url),
			"utf8",
		).replace(/\/\*\*.*?\*\//s, ""),
		road,
	);
	const display = readFileSync(
		new URL("./coarse_osm_filled_display_v1.ts", import.meta.url),
		"utf8",
	)
		.replace(/\/\*\*.*?\*\//s, "")
		.replace(
			"export function filledDisplay(",
			"export function diagnosticFilledDisplay(",
		)
		.replace("field.horizonTicks > 345600", "field.horizonTicks > 432000");
	assert.equal(
		readFileSync(
			new URL("./coarse_osm_diagnostic_display_v1.ts", import.meta.url),
			"utf8",
		).replace(/\/\*\*.*?\*\//s, ""),
		display,
	);
});
test("900-minute diagnostics preserve every 720-minute field/shape and production ceiling", () => {
	const p = example();
	for (const maxTicks of [1000, 345600]) {
		const options = { maxTicks, maxHeapEntries: 256 };
		const before = computeRoadField(
				p.graph,
				p.geometry,
				p.source.snap,
				0,
				options,
			),
			after = computeDiagnosticRoadField(
				p.graph,
				p.geometry,
				p.source.snap,
				0,
				options,
			);
		assert.deepEqual(after, before);
		const displayOptions = { maxCells: 10000, heapEntries: 1000 };
		assert.deepEqual(
			diagnosticFilledDisplay(
				p.graph,
				p.geometry,
				p.geography,
				p.source,
				after,
				displayOptions,
			).output,
			filledDisplay(
				p.graph,
				p.geometry,
				p.geography,
				p.source,
				before,
				displayOptions,
			).output,
		);
	}
	assert.throws(
		() =>
			computeRoadField(p.graph, p.geometry, p.source.snap, 0, {
				maxTicks: 432000,
			}),
		/horizon/,
	);
	const field = computeDiagnosticRoadField(
		p.graph,
		p.geometry,
		p.source.snap,
		0,
		{ maxTicks: 432000, maxHeapEntries: 256 },
	);
	assert.equal(field.labels[0], 400000);
	assert.throws(
		() => filledDisplay(p.graph, p.geometry, p.geography, p.source, field),
		/mismatch/,
	);
});
test("point finish pays terminal/local path, competes with road foot and preserves zero input", () => {
	const p = example(),
		field = computeDiagnosticRoadField(p.graph, p.geometry, p.source.snap, 0, {
			maxTicks: 800,
			maxHeapEntries: 256,
		});
	let called = false;
	diagnosticFilledDisplay(p.graph, p.geometry, p.geography, p.source, field, {
		maxCells: 10000,
		heapEntries: 1000,
		probe: (grid) => {
			called = true;
			assert.equal(
				displayPointTiming(
					p.graph,
					p.geometry,
					p.geography,
					field,
					grid,
					p.source.origin,
					p.source.origin,
					null,
				).ticks,
				0,
			);
			const target = [0.0025, 0.0025] as const;
			const local = displayPointTiming(
				p.graph,
				p.geometry,
				p.geography,
				field,
				grid,
				p.source.origin,
				target,
				null,
			);
			assert.equal(local.kind, "local-grid");
			assert.ok(local.ticks !== null && local.ticks > 0);
			assert.ok(local.localWitness);
			assert.equal(
				local.localWitness.terminalTicks +
					8 * (local.localWitness.edgeSeconds + local.localWitness.seedSeconds),
				local.ticks,
			);
			const withRoad = displayPointTiming(
				p.graph,
				p.geometry,
				p.geography,
				field,
				grid,
				p.source.origin,
				target,
				{ ...p.source, origin: target, connectorTicks: 1 },
			);
			assert.equal(withRoad.kind, "road-foot");
			assert.equal(withRoad.ticks, 1);
			const outside = displayPointTiming(
				p.graph,
				p.geometry,
				p.geography,
				field,
				grid,
				p.source.origin,
				[0.19, 0.19],
				null,
			);
			assert.equal(outside.ticks, null);
		},
	});
	assert.ok(called);
});
