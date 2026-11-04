import assert from "node:assert/strict";
import test from "node:test";
import {
	geography,
	prepared,
	rectangle,
} from "./coarse_osm_access_fixture_v2.ts";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import { computeDiagnosticAccessRoadField } from "./coarse_osm_access_road_field_v1.ts";
import { cellAt } from "./coarse_osm_display_grid_v1.ts";
import { displayPointWitness } from "./coarse_osm_local_witness_v1.ts";
import { connectOriginAccessV3 } from "./coarse_osm_origin_access_v3.ts";
import { searchRoadWitness } from "./coarse_osm_road_witness_v1.ts";
import {
	createSeedTrace,
	offlineTraceAccessDisplay,
} from "./coarse_osm_trace_display_v1.ts";

function example(
	x = 0,
	origin: readonly [number, number] = [0, 0.0001],
	horizon = 12000,
) {
	const p = prepared(
			[
				[x, 0],
				[x + 0.03, 0],
			],
			[[0, 1]],
		),
		geo = geography();
	const access = connectOriginAccessV3(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		geo,
		origin,
	);
	assert.ok(access.primary);
	const primary = access.primary,
		starts = accessStarts(primary, access.connections),
		field = computeDiagnosticAccessRoadField(p.graph, p.geometry, starts, {
			maxTicks: horizon,
			maxHeapEntries: 256,
		}),
		trace = createSeedTrace(10000);
	return { ...p, geo, primary, accessInputs: starts, field, trace, origin };
}
test("local suffix finds its actual road sample and reconciles all positive rounding", () => {
	const p = example();
	let checked = false;
	offlineTraceAccessDisplay(p.graph, p.geometry, p.geo, p.primary, p.field, {
		seedTrace: p.trace,
		maxCells: 10000,
		heapEntries: 1000,
		probe: (grid) => {
			const point = displayPointWitness(
				p.graph,
				p.geometry,
				p.geo,
				p.field,
				grid,
				p.trace,
				p.origin,
				[0.0325, 0.0025],
				null,
			);
			assert.equal(point.measured.kind, "local-grid");
			assert.ok(point.roadTarget && point.fieldRoadTicks !== null);
			const road = searchRoadWitness(
				p.graph,
				p.geometry,
				p.accessInputs,
				point.roadTarget,
				{ maxTicks: 12000, maxHeapEntries: 256 },
			);
			assert.ok(road.ticks !== null);
			assert.ok(
				point.fieldRoadTicks >= road.ticks &&
					point.fieldRoadTicks <= road.ticks + 7,
			);
			assert.equal(
				point.fieldRoadTicks +
					Object.values(point.components).reduce((a, b) => a + b, 0),
				point.measured.ticks,
			);
			assert.ok(
				Object.values(point.components).every(
					(ticks) => Number.isInteger(ticks) && ticks >= 0,
				),
			);
			assert.ok(point.components.roadSeedLinkTicks > 0);
			assert.ok(point.coordinates.length >= 3);
			checked = true;
		},
	});
	assert.ok(checked);
});
test("primary road-foot finishes retain their own entire terminal price", () => {
	const p = example(),
		target = [0.03, 0] as const,
		targetAccess = connectOriginAccessV3(
			p.graph,
			p.geometry,
			p.keys,
			p.starts,
			p.geo,
			target,
		);
	assert.ok(targetAccess.primary);
	let checked = false;
	offlineTraceAccessDisplay(p.graph, p.geometry, p.geo, p.primary, p.field, {
		seedTrace: p.trace,
		maxCells: 10000,
		heapEntries: 1000,
		probe: (grid) => {
			const point = displayPointWitness(
				p.graph,
				p.geometry,
				p.geo,
				p.field,
				grid,
				p.trace,
				p.origin,
				target,
				targetAccess.primary,
			);
			assert.equal(point.measured.kind, "road-foot");
			assert.ok(point.roadTarget);
			assert.equal(
				point.components.terminalTicks,
				targetAccess.primary?.connectorTicks,
			);
			assert.equal(point.components.gridTravelTicks, 0);
			checked = true;
		},
	});
	assert.ok(checked);
});
test("the paid input-local branch needs no invented road path", () => {
	const p = example(0.008, [0, 0], 800);
	assert.ok(p.primary.connectorTicks > 800);
	let checked = false;
	offlineTraceAccessDisplay(p.graph, p.geometry, p.geo, p.primary, p.field, {
		seedTrace: p.trace,
		maxCells: 10000,
		heapEntries: 1000,
		probe: (grid) => {
			const point = displayPointWitness(
				p.graph,
				p.geometry,
				p.geo,
				p.field,
				grid,
				p.trace,
				p.origin,
				[0.0025, 0.0025],
				null,
			);
			assert.equal(point.measured.kind, "local-grid");
			assert.equal(point.roadTarget, null);
			assert.ok(point.components.inputLocalTicks > 0);
			assert.equal(
				Object.values(point.components).reduce((a, b) => a + b, 0),
				point.measured.ticks,
			);
			checked = true;
		},
	});
	assert.ok(checked);
});
test("missing road seed metadata fails instead of substituting another route", () => {
	const p = example();
	let checked = false;
	offlineTraceAccessDisplay(p.graph, p.geometry, p.geo, p.primary, p.field, {
		seedTrace: p.trace,
		maxCells: 10000,
		heapEntries: 1000,
		probe: (grid) => {
			const target = [0.0325, 0.0025] as const,
				cell = cellAt(grid.frame, target);
			assert.ok(cell >= 0);
			const point = displayPointWitness(
				p.graph,
				p.geometry,
				p.geo,
				p.field,
				grid,
				p.trace,
				p.origin,
				target,
				null,
			);
			assert.ok(point.measured.localWitness && point.roadTarget);
			p.trace.arcs[point.measured.localWitness.seedCell] = 0xffffffff;
			assert.throws(
				() =>
					displayPointWitness(
						p.graph,
						p.geometry,
						p.geo,
						p.field,
						grid,
						p.trace,
						p.origin,
						target,
						null,
					),
				/missing road sample/,
			);
			checked = true;
		},
	});
	assert.ok(checked);
});
test("independent suffix replay checks geography instead of trusting cached land bits", () => {
	const p = example();
	let checked = false;
	offlineTraceAccessDisplay(p.graph, p.geometry, p.geo, p.primary, p.field, {
		seedTrace: p.trace,
		maxCells: 10000,
		heapEntries: 1000,
		probe: (grid) => {
			p.geo.lakes = [[rectangle(-0.05, -0.05, 0.05, 0.05)]];
			assert.throws(
				() =>
					displayPointWitness(
						p.graph,
						p.geometry,
						p.geo,
						p.field,
						grid,
						p.trace,
						p.origin,
						[0.0325, 0.0025],
						null,
					),
				/water/,
			);
			checked = true;
		},
	});
	assert.ok(checked);
});
