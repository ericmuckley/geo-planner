import assert from "node:assert/strict";
import test from "node:test";
import { diagnosticAccessFilledDisplay } from "./coarse_osm_access_display_v1.ts";
import { geography, prepared } from "./coarse_osm_access_fixture_v2.ts";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import {
	arrivalAtAccessPosition,
	computeDiagnosticAccessRoadField,
} from "./coarse_osm_access_road_field_v1.ts";
import { accessDisplayPointTiming } from "./coarse_osm_access_timing_v1.ts";
import { center, nibble } from "./coarse_osm_display_grid_v1.ts";
import { connectOriginAccessV3 } from "./coarse_osm_origin_access_v3.ts";
import { connectorPrice } from "./coarse_osm_origin_connections_v1.ts";
import {
	createSeedTrace,
	offlineTraceAccessDisplay,
} from "./coarse_osm_trace_display_v1.ts";
import { witnessPositionCoordinate } from "./coarse_osm_witness_geometry_v1.ts";

test("instrumentation preserves output and every final point time byte-for-byte", () => {
	const p = prepared(
			[
				[-0.005, 0],
				[0.005, 0],
				[0.004, -0.01],
				[0.004, 0.01],
			],
			[
				[0, 1],
				[2, 3],
			],
		),
		geo = geography(),
		origin = [0, 0.0002] as const;
	const access = connectOriginAccessV3(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		geo,
		origin,
	);
	assert.ok(access.primary);
	const starts = accessStarts(access.primary, access.connections),
		field = computeDiagnosticAccessRoadField(p.graph, p.geometry, starts, {
			maxTicks: 7200,
			maxHeapEntries: 256,
		}),
		trace = createSeedTrace(10000);
	let before: unknown,
		after: unknown,
		seeds = 0;
	const original = diagnosticAccessFilledDisplay(
		p.graph,
		p.geometry,
		geo,
		access.primary,
		field,
		{
			maxCells: 10000,
			heapEntries: 1000,
			probe: (grid) => {
				before = accessDisplayPointTiming(
					p.graph,
					p.geometry,
					geo,
					field,
					grid,
					origin,
					[0.0125, 0.0125],
					null,
				);
			},
		},
	);
	const measured = offlineTraceAccessDisplay(
		p.graph,
		p.geometry,
		geo,
		access.primary,
		field,
		{
			seedTrace: trace,
			maxCells: 10000,
			heapEntries: 1000,
			probe: (grid) => {
				after = accessDisplayPointTiming(
					p.graph,
					p.geometry,
					geo,
					field,
					grid,
					origin,
					[0.0125, 0.0125],
					null,
				);
				for (let i = 0; i < grid.times.length; i++)
					if (nibble(grid.parents, i) === 8) {
						const point = {
							canonicalArc: trace.arcs[i],
							segment: trace.segments[i],
							segmentFraction: trace.fractions[i],
						};
						assert.ok(point.canonicalArc !== 0xffffffff);
						const road = arrivalAtAccessPosition(
							p.graph,
							p.geometry,
							field,
							point,
						);
						assert.ok(road !== null);
						const coordinate = witnessPositionCoordinate(p.geometry, point),
							price = connectorPrice(coordinate, center(grid.frame, i));
						assert.equal(
							grid.times[i],
							Math.ceil(road / 8) + Math.ceil(price.ticks / 8),
						);
						seeds++;
					}
			},
		},
	);
	assert.deepEqual(measured.output, original.output);
	assert.deepEqual(after, before);
	assert.ok(seeds > 0);
	assert.equal(
		measured.stats.maximumBackingBufferBytes,
		original.stats.maximumBackingBufferBytes + 140000,
	);
	assert.equal(
		measured.stats.productionAlgorithmBackingBufferBytes,
		original.stats.maximumBackingBufferBytes,
	);
});
test("trace metadata remains separate from input seeds, coverage-only and water propagation", () => {
	const p = prepared(
			[
				[-0.005, 0],
				[0.005, 0],
			],
			[[0, 1]],
		),
		geo = geography();
	geo.boundary = [];
	const primary = {
		origin: [0, 0] as const,
		snap: {
			canonicalArc: 0,
			segment: 0,
			segmentFraction: 0.5,
			coordinate: [0, 0] as const,
			distanceMeters: 0,
			forwardProgress: 0.5,
			backwardProgress: 0,
		},
		connectorTicks: 0,
		connectorMeters: 0,
		kind: "modeled-road" as const,
	};
	const field = computeDiagnosticAccessRoadField(
			p.graph,
			p.geometry,
			[{ position: primary.snap, initialTicks: 0 }],
			{ maxTicks: 1000, maxHeapEntries: 256 },
		),
		trace = createSeedTrace(10000);
	const output = offlineTraceAccessDisplay(
		p.graph,
		p.geometry,
		geo,
		primary,
		field,
		{ seedTrace: trace, maxCells: 10000, heapEntries: 1000 },
	);
	assert.equal(output.stats.localCells, 0);
	assert.ok(output.stats.roadOnlyCells > 0);
	assert.ok(trace.arcs.every((v) => v === 0xffffffff));
});
test("trace arrays have explicit offline caps and reject mismatched or oversized backing", () => {
	assert.throws(() => createSeedTrace(2500001), /cap/);
	const p = prepared(
			[
				[-0.001, 0],
				[0.001, 0],
			],
			[[0, 1]],
		),
		geo = geography(),
		access = connectOriginAccessV3(
			p.graph,
			p.geometry,
			p.keys,
			p.starts,
			geo,
			[0, 0],
		);
	assert.ok(access.primary);
	const field = computeDiagnosticAccessRoadField(
		p.graph,
		p.geometry,
		accessStarts(access.primary, access.connections),
		{ maxTicks: 500, maxHeapEntries: 256 },
	);
	assert.throws(
		() =>
			offlineTraceAccessDisplay(
				p.graph,
				p.geometry,
				geo,
				access.primary,
				field,
				{ seedTrace: createSeedTrace(5), maxCells: 10000, heapEntries: 1000 },
			),
		/shape/,
	);
	const trace = createSeedTrace(10000);
	trace.arcs = new Uint32Array(new ArrayBuffer(128 * 1024 ** 2), 0, 10000);
	assert.throws(
		() =>
			offlineTraceAccessDisplay(
				p.graph,
				p.geometry,
				geo,
				access.primary,
				field,
				{ seedTrace: trace, maxCells: 10000, heapEntries: 1000 },
			),
		/offline.*cap/i,
	);
});
