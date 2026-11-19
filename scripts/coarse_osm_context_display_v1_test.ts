import assert from "node:assert/strict";
import test from "node:test";
import {
	accessFilledDisplay,
	diagnosticAccessFilledDisplay,
} from "./coarse_osm_access_display_v3.ts";
import { geography } from "./coarse_osm_access_fixture_v2.ts";
import { arrivalAtAccessPosition } from "./coarse_osm_access_road_field_v1.ts";
import { accessDisplayPointTiming } from "./coarse_osm_access_timing_v2.ts";
import {
	withAccessContextRoadField,
	withDiagnosticContextRoadField,
} from "./coarse_osm_context_road_field_v1.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
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
import { legacyRoutingGeography } from "./coarse_osm_routing_geography_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { sphericalDistance } from "./coarse_osm_spherical_v1.ts";
import {
	type ContextRule,
	contextFiles,
} from "./coarse_osm_turn_context_fixture_v1.ts";
import { TurnContexts } from "./coarse_osm_turn_contexts_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

function prepared(
	points: Coordinate[],
	edges: TestArc[],
	rules: ContextRule[] = [],
) {
	const raw = fixture(points.length, edges);
	raw["routing/xy.i32"] = words(
		points.flatMap((p) => p.map((v) => Math.round(v * 1e7))),
		4,
		true,
	);
	const graph = new PackedCarGraph(raw);
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((n) => [n, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	const keys: number[] = [],
		lengths: number[] = [];
	edges.forEach(([a, b], i) => {
		const meters = sphericalDistance(points[a], points[b]);
		if (meters > 1000) {
			keys.push(i);
			lengths.push(Math.ceil(meters / 8) + 1);
		}
	});
	files["geometry/long-keys.u24"] = packUint24(keys);
	files["geometry/long-lengths.u16"] = words(lengths, 2);
	const contexts = new TurnContexts(
		graph.arcs,
		contextFiles(
			edges.map(([tail, head], i) => ({ tail, head, way: 10 * (i + 1) })),
			rules,
		),
	);
	const source: OriginConnection = {
		origin: points[0],
		snap: {
			canonicalArc: 0,
			segment: 0,
			segmentFraction: 0,
			coordinate: points[0],
			distanceMeters: 0,
			forwardProgress: 0,
			backwardProgress: 0,
		},
		connectorTicks: 0,
		connectorMeters: 0,
		kind: "modeled-road",
	};
	return {
		graph,
		geometry: new PaidRoadGeometry(graph, files),
		contexts,
		source,
	};
}

test("fresh context-field grid propagation responds to changed road costs instead of frozen fallback times", () => {
	function estimate(cost: number) {
		const p = prepared(
				[
					[0, 0],
					[0.04, 0],
				],
				[[0, 1, cost]],
			),
			geo = legacyRoutingGeography(geography());
		return withDiagnosticContextRoadField(
			p.graph,
			p.geometry,
			p.contexts,
			[{ position: p.source.snap, initialTicks: 0 }],
			(field) => {
				const before = field.labels.slice();
				const timings: number[] = [];
				diagnosticAccessFilledDisplay(
					p.graph,
					p.geometry,
					geo,
					p.source,
					field,
					{
						maxCells: 10000,
						heapEntries: 1000,
						probe: (grid) => {
							const ticks = accessDisplayPointTiming(
								p.graph,
								p.geometry,
								geo,
								field,
								grid,
								p.source.origin,
								[0.04, 0],
								null,
							).ticks;
							assert.ok(ticks !== null);
							timings.push(ticks);
						},
					},
				);
				assert.deepEqual(field.labels, before);
				assert.equal(timings.length, 1);
				return timings[0];
			},
			{ maxTicks: 4800, maxHeapEntries: 256 },
		);
	}
	const before = estimate(600),
		after = estimate(1200);
	assert.ok(after > before, `${before} -> ${after}`);
	assert.equal(
		Math.min(before, after),
		before,
		"reusing the frozen grid would hide the cost increase",
	);
});

test("production display preserves prohibited history completions and releases its borrowed field", () => {
	const p = prepared(
		[
			[0, 0],
			[0.004, 0],
			[0.008, 0],
			[0.012, 0],
		],
		[
			[0, 1, 240],
			[1, 2, 240],
			[2, 3, 240],
		],
		[[10, 20, 30]],
	);
	const released: { labels: Uint32Array }[] = [];
	withAccessContextRoadField(
		p.graph,
		p.geometry,
		p.contexts,
		[{ position: p.source.snap, initialTicks: 0 }],
		(field) => {
			released.push(field);
			const target = { canonicalArc: 2, segment: 0, segmentFraction: 1 };
			assert.equal(
				arrivalAtAccessPosition(p.graph, p.geometry, field, target),
				null,
			);
			const before = field.labels.slice();
			accessFilledDisplay(
				p.graph,
				p.geometry,
				legacyRoutingGeography(geography()),
				p.source,
				field,
				{
					maxCells: 10000,
					heapEntries: 1000,
				},
			);
			assert.deepEqual(field.labels, before);
			assert.equal(
				arrivalAtAccessPosition(p.graph, p.geometry, field, target),
				null,
			);
		},
		{ maxTicks: 4800, maxHeapEntries: 256 },
	);
	assert.equal(released.length, 1);
	assert.equal(released[0].labels.length, 0);
});
