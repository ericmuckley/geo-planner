import assert from "node:assert/strict";
import test from "node:test";
import {
	accessFilledDisplay,
	diagnosticAccessFilledDisplay,
} from "./coarse_osm_access_display_v1.ts";
import { geography, prepared } from "./coarse_osm_access_fixture_v2.ts";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import {
	type AccessStart,
	computeAccessRoadField,
	computeDiagnosticAccessRoadField,
} from "./coarse_osm_access_road_field_v1.ts";
import { accessDisplayPointTiming } from "./coarse_osm_access_timing_v1.ts";
import { filledDisplay } from "./coarse_osm_filled_display_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
} from "./coarse_osm_origin_connections_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import { computeRoadField } from "./coarse_osm_road_field_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";

const connection = (
	arc: number,
	fraction: number,
	origin: Coordinate,
	coordinate: Coordinate,
): OriginConnection => {
	const price = connectorPrice(origin, coordinate);
	return {
		origin,
		snap: {
			canonicalArc: arc,
			segment: 0,
			segmentFraction: fraction,
			coordinate,
			distanceMeters: price.meters,
			forwardProgress: fraction,
			backwardProgress: 0,
		},
		connectorTicks: price.ticks,
		connectorMeters: price.meters,
		kind: price.meters <= 1 ? "modeled-road" : "land-connector",
	};
};
test("qualified start inputs preserve the primary and reject a mixed origin", () => {
	const first = connection(1, 0.5, [0, 0], [0, 0]),
		second = connection(2, 0.25, [0, 0], [0.001, 0]);
	const starts = accessStarts(first, [second, first]);
	assert.equal(starts.length, 2);
	assert.deepEqual(starts[0], { position: first.snap, initialTicks: 0 });
	assert.throws(() => accessStarts(first, [second]), /missing primary/);
	assert.throws(
		() => accessStarts(first, [first, { ...second, origin: [1, 1] }]),
		/origin mismatch/,
	);
});
test("single-source geometry/field semantics remain byte-equal to the sealed display", () => {
	const p = prepared(
			[
				[-0.004, 0],
				[0.004, 0],
			],
			[[0, 1]],
		),
		geo = geography();
	for (const fraction of [0, 0.3, 0.75, 1])
		for (const horizon of [500, 2400]) {
			const point = [-0.004 + 0.008 * fraction, 0] as const,
				primary = connection(0, fraction, point, point),
				starts = [{ position: primary.snap, initialTicks: 0 }];
			const before = computeRoadField(p.graph, p.geometry, primary.snap, 0, {
				maxTicks: horizon,
				maxHeapEntries: 256,
			});
			const after = computeAccessRoadField(p.graph, p.geometry, starts, {
				maxTicks: horizon,
				maxHeapEntries: 256,
			});
			const opts = { maxCells: 10000, heapEntries: 1000 };
			assert.deepEqual(
				accessFilledDisplay(p.graph, p.geometry, geo, primary, after, opts)
					.output,
				filledDisplay(p.graph, p.geometry, geo, primary, before, opts).output,
			);
		}
});
test("a secondary frontier-only source gets its own envelope and paid samples", () => {
	const p = prepared(
			[
				[-0.001, 0],
				[0.001, 0],
				[0.0027, -0.01],
				[0.0027, 0.01],
			],
			[
				[0, 1],
				[2, 3],
			],
		),
		origin = [0, 0] as const;
	const firstArc = Array.from({ length: p.graph.arcs }, (_, i) => i).find(
		(i) => p.graph.coordinate(p.graph.arcTail(i))[0] < 0,
	);
	assert.ok(firstArc !== undefined);
	const secondArc = 1 - firstArc,
		primary = connection(firstArc, 0.5, origin, origin),
		secondary = connection(secondArc, 0.5, origin, [0.0027, 0]);
	const starts = [primary, secondary].map((c) => ({
		position: c.snap,
		initialTicks: c.connectorTicks,
	}));
	const field = computeAccessRoadField(p.graph, p.geometry, starts, {
		maxTicks: 640,
		maxHeapEntries: 256,
	});
	assert.equal(field.labels[secondArc], 0xffffffff);
	const vertices = field.vertexArrivalSeconds.slice(),
		labels = field.labels.slice();
	const result = accessFilledDisplay(
		p.graph,
		p.geometry,
		geography(),
		primary,
		field,
		{ maxCells: 10000, heapEntries: 1000 },
	);
	assert.deepEqual(field.labels, labels);
	assert.deepEqual(field.vertexArrivalSeconds, vertices);
	assert.ok(result.frame.height >= 4);
	assert.ok(
		result.output.coordinates.flat(2).some((point) => point[1] >= 0.01),
	);
});
test("all initial vertex summaries restore on borrowed-heap success and cancellation", () => {
	const graph = new PackedCarGraph(
		fixture(8000, [
			[0, 1, 100],
			[1, 2, 100],
		]),
	);
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((n) => [n, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = new Uint8Array(4);
	const geometry = new PaidRoadGeometry(graph, files),
		primary = connection(0, 0, [0, 0], [0, 0]);
	for (const cancel of [false, true]) {
		const starts: AccessStart[] = [
			{ position: primary.snap, initialTicks: 0 },
			{
				position: { canonicalArc: 1, segment: 0, segmentFraction: 0 },
				initialTicks: 20,
			},
		];
		const field = computeAccessRoadField(graph, geometry, starts, {
				maxTicks: 2400,
				maxHeapEntries: 256,
			}),
			before = field.vertexArrivalSeconds.slice();
		const run = () =>
			accessFilledDisplay(graph, geometry, geography(), primary, field, {
				maxCells: 10000,
				heapEntries: 1000,
				check: () => {
					if (
						cancel &&
						field.vertexArrivalSeconds.some((v, i) => v !== before[i])
					)
						throw new Error("cancel");
				},
			});
		if (cancel) assert.throws(run, /cancel/);
		else assert.equal(run().stats.borrowedVertexWorkspace, true);
		assert.deepEqual(field.vertexArrivalSeconds, before);
	}
});
test("named900-minute diagnostic and paid point suffix remain separate from720 display", () => {
	const p = prepared(
			[
				[-0.004, 0],
				[0.004, 0],
			],
			[[0, 1]],
		),
		primary = connection(0, 0.5, [0, 0], [0, 0]);
	const field = computeDiagnosticAccessRoadField(
		p.graph,
		p.geometry,
		[{ position: primary.snap, initialTicks: 0 }],
		{ maxTicks: 432000, maxHeapEntries: 256 },
	);
	assert.throws(
		() => accessFilledDisplay(p.graph, p.geometry, geography(), primary, field),
		/mismatch/,
	);
	let checked = false;
	diagnosticAccessFilledDisplay(
		p.graph,
		p.geometry,
		geography(),
		primary,
		field,
		{
			maxCells: 10000,
			heapEntries: 1000,
			probe: (grid) => {
				const point = accessDisplayPointTiming(
					p.graph,
					p.geometry,
					geography(),
					field,
					grid,
					[0, 0],
					[0.0025, 0.0025],
					null,
				);
				assert.ok(point.ticks !== null && point.ticks > 0);
				assert.ok(point.localWitness);
				checked = true;
			},
		},
	);
	assert.ok(checked);
});
