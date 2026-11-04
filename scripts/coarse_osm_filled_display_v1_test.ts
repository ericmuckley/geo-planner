import assert from "node:assert/strict";
import test from "node:test";
import {
	cellContours,
	containsPolygon,
} from "../src/server/coarse-contours.ts";
import {
	landConnection,
	prepareGeography,
} from "../src/server/coarse-geography.ts";
import { boundedContours } from "./coarse_osm_display_contours_v1.ts";
import {
	bit,
	center,
	DIRECTIONS,
	DisplayLimit,
	DisplayQueue,
	fillLocal,
	hasLink,
	localCosts,
	makeFrame,
	nibble,
	rasterLand,
	rasterLinks,
	setBit,
	setNibble,
} from "./coarse_osm_display_grid_v1.ts";
import {
	filledDisplay,
	restoreVertices,
	roadCoordinate,
} from "./coarse_osm_filled_display_v1.ts";
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
import { sphericalDistance } from "./coarse_osm_spherical_v1.ts";

const rect = (w: number, s: number, e: number, n: number) => [
	[w, s],
	[e, s],
	[e, n],
	[w, n],
	[w, s],
];
const geography = (): OriginGeography => ({
	bounds: [-0.2, -0.2, 0.2, 0.2],
	boundary: [[rect(-0.2, -0.2, 0.2, 0.2)]],
	lakes: [],
});
function grid(geo: OriginGeography, step = 5000) {
	const frame = makeFrame(geo.bounds, step),
		count = frame.width * frame.height;
	const land = new Uint8Array(Math.ceil(count / 8)),
		boundary = land.slice(),
		coverage = land.slice();
	const links = new Uint8Array(Math.ceil(count / 2)),
		parents = links.slice().fill(255);
	const horizontal = new Uint16Array(frame.height),
		diagonal = horizontal.slice();
	rasterLand(frame, geo, land, boundary, new Uint8Array(frame.width), () => {});
	rasterLinks(frame, geo, land, boundary, links, () => {});
	const vertical = localCosts(frame, horizontal, diagonal);
	return {
		frame,
		count,
		land,
		boundary,
		links,
		parents,
		horizontal,
		diagonal,
		vertical,
		coverage,
	};
}

test("scanline land equals original membership across unions, holes and narrow channels", () => {
	const geo = geography();
	geo.boundary = [
		[rect(-0.2, -0.2, 0.12, 0.2), rect(-0.13, -0.09, -0.07, 0.11)],
		[rect(-0.03, -0.2, 0.2, 0.12)],
	];
	geo.lakes = [
		[rect(-0.0001, -0.2, 0.0001, 0.2)],
		[rect(0.06, 0.04, 0.13, 0.16), rect(0.08, 0.06, 0.11, 0.1)],
	];
	prepareGeography(geo);
	const g = grid(geo);
	let checked = 0,
		blockedNarrow = 0;
	for (let i = 0; i < g.count; i++) {
		const p = center(g.frame, i);
		assert.equal(Boolean(bit(g.land, i)), landConnection(geo, p, p));
		const x = i % g.frame.width,
			y = Math.floor(i / g.frame.width);
		for (let d = 0; d < 4; d++) {
			const [dx, dy] = DIRECTIONS[d],
				nx = x + dx,
				ny = y + dy;
			if (nx < 0 || nx >= g.frame.width || ny >= g.frame.height) continue;
			const j = ny * g.frame.width + nx,
				q = center(g.frame, j);
			const expected =
				!!bit(g.land, i) && !!bit(g.land, j) && landConnection(geo, p, q);
			assert.equal(hasLink(g.links, i, j, d), expected);
			checked++;
			if (p[0] < 0 && q[0] > 0 && bit(g.land, i) && bit(g.land, j) && !expected)
				blockedNarrow++;
		}
	}
	assert.ok(checked > 20000);
	assert.ok(blockedNarrow > 50);
});

test("bounded contours match deployed cell unions for holes and 250 seeded random masks", () => {
	let state = 4751;
	for (let run = 0; run < 250; run++) {
		const width = 2 + (run % 16),
			height = 2 + (run % 13),
			mask = new Uint8Array(width * height);
		for (let i = 0; i < mask.length; i++) {
			state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
			mask[i] = state % 3 === 0 ? 1 : 0;
		}
		const frame = { west: 0, south: 0, step: 5000, width, height };
		const got = boundedContours(
			mask,
			new Uint8Array((width + 1) * (height + 1)),
			frame,
			{ edges: 400000, rings: 4096, vertices: 100000 },
			() => {},
		);
		assert.deepEqual(
			got.polygons,
			cellContours(mask, width, height, 0, 0, 0.005),
		);
	}
});

test("exact local solver matches independent relaxation and every paid parent sum", () => {
	const geo = geography();
	geo.lakes = [[rect(-0.02, -0.15, 0.02, 0.15)]];
	const g = grid(geo, 10000),
		times = new Uint16Array(g.count).fill(65535);
	for (const i of [g.frame.width + 1, g.count - 2 * g.frame.width - 2]) {
		times[i] = i % 19;
		setNibble(g.parents, i, 8);
	}
	const expected = Array.from(times);
	for (let pass = 0; pass < g.count; pass++) {
		let changed = false;
		for (let i = 0; i < g.count; i++)
			for (let d = 0; d < 8; d++) {
				const x = i % g.frame.width,
					y = Math.floor(i / g.frame.width),
					[dx, dy] = DIRECTIONS[d],
					nx = x + dx,
					ny = y + dy;
				if (nx < 0 || ny < 0 || nx >= g.frame.width || ny >= g.frame.height)
					continue;
				const j = ny * g.frame.width + nx;
				if (!hasLink(g.links, i, j, d)) continue;
				const cost =
					dy === 0
						? g.horizontal[y]
						: dx === 0
							? g.vertical
							: g.diagonal[Math.min(y, ny)];
				if (expected[i] + cost <= 1800 && expected[i] + cost < expected[j]) {
					expected[j] = expected[i] + cost;
					changed = true;
				}
			}
		if (!changed) break;
	}
	fillLocal(
		g.frame,
		times,
		g.parents,
		g.links,
		g.horizontal,
		g.diagonal,
		g.vertical,
		1800,
		new DisplayQueue(new Uint32Array(10000), new Uint32Array(10000)),
		() => {},
	);
	assert.deepEqual(Array.from(times), expected);
	for (let i = 0; i < g.count; i++)
		if (times[i] !== 65535 && nibble(g.parents, i) < 8) {
			const d = nibble(g.parents, i),
				[dx, dy] = DIRECTIONS[d],
				y = Math.floor(i / g.frame.width),
				j = i + dy * g.frame.width + dx;
			const cost =
				dy === 0
					? g.horizontal[y]
					: dx === 0
						? g.vertical
						: g.diagonal[Math.min(y, y + dy)];
			assert.ok(hasLink(g.links, i, j, d));
			assert.equal(times[i], times[j] + cost);
			assert.ok(times[j] < times[i]);
		}
});

function example(vertices = 2, horizon = 800, fraction = 0) {
	const files = fixture(vertices, [[0, 1, 1600]]);
	files["routing/xy.i32"] = words(
		Array.from({ length: vertices }, (_, i) =>
			i === 1 ? [1000000, 0] : [0, 0],
		).flat(),
		4,
		true,
	);
	const graph = new PackedCarGraph(files);
	const shapes = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	shapes["geometry/curve-offsets.u32"] = words([0], 4);
	const geometry = new PaidRoadGeometry(graph, shapes);
	const snap = {
		canonicalArc: 0,
		segment: 0,
		segmentFraction: fraction,
		coordinate: [fraction * 0.1, 0] as const,
		distanceMeters: 0,
		forwardProgress: fraction,
		backwardProgress: 0,
	};
	const connection: OriginConnection = {
		origin: snap.coordinate,
		snap,
		connectorMeters: 0,
		connectorTicks: 0,
		kind: "modeled-road",
	};
	const field = computeRoadField(graph, geometry, snap, 0, {
		maxTicks: horizon,
		maxHeapEntries: 256,
	});
	return { graph, geometry, connection, field };
}

test("frontier-only roads shade without unpaid head or forbidden upstream source prefix", () => {
	const p = example(2, 240, 0.75),
		geo = geography();
	geo.boundary = []; // all omitted by the coarse mask: coverage may shade, never propagate.
	const result = filledDisplay(
		p.graph,
		p.geometry,
		geo,
		p.connection,
		p.field,
		{
			maxCells: 10000,
			heapEntries: 1000,
			probe: (g) => {
				assert.equal(g.times.filter((v) => v !== 65535).length, 0);
				for (let i = 0; i < g.times.length; i++)
					if (bit(g.coverage, i))
						assert.ok(center(g.frame, i)[0] >= 0.075 - 0.005);
			},
		},
	);
	assert.equal(result.stats.localCells, 0);
	assert.ok(result.stats.roadOnlyCells > 1);
	assert.equal(p.field.vertexArrivalSeconds[1], 65535);
	assert.ok(result.output.coordinates.length > 0);
});

test("borrowed vertex summaries restore byte-for-byte on success, heap failure and thrown cancellation", () => {
	for (const mode of ["success", "capacity", "cancel"] as const) {
		const p = example(8000, 2400),
			before = p.field.vertexArrivalSeconds.slice();
		const options = {
			maxCells: 10000,
			heapEntries: mode === "capacity" ? 1 : 1000,
			check: () => {
				if (
					mode === "cancel" &&
					p.field.vertexArrivalSeconds.some((v, i) => v !== before[i])
				)
					throw new Error("cancelled");
			},
		};
		if (mode === "success")
			assert.equal(
				filledDisplay(
					p.graph,
					p.geometry,
					geography(),
					p.connection,
					p.field,
					options,
				).stats.borrowedVertexWorkspace,
				true,
			);
		else
			assert.throws(() =>
				filledDisplay(
					p.graph,
					p.geometry,
					geography(),
					p.connection,
					p.field,
					options,
				),
			);
		assert.deepEqual(p.field.vertexArrivalSeconds, before);
	}
});

test("scratch preflight and contour/output caps reject before excessive allocation", () => {
	const p = example();
	p.field.stats.maximumBackingBufferBytes = 67108864;
	assert.throws(
		() =>
			filledDisplay(p.graph, p.geometry, geography(), p.connection, p.field),
		/scratch/,
	);
	const frame = { west: 0, south: 0, step: 5000, width: 3, height: 3 },
		mask = Uint8Array.from([1, 0, 1, 0, 1, 0, 1, 0, 1]);
	assert.throws(
		() =>
			boundedContours(
				mask,
				new Uint8Array(16),
				frame,
				{ edges: 2, rings: 10, vertices: 50 },
				() => {},
			),
		DisplayLimit,
	);
});

test("restored summaries include source vertices, and interpolation uses paid minor arcs", () => {
	const p = example(2, 2400);
	p.field.vertexArrivalSeconds.fill(12345);
	restoreVertices(p.graph, p.field);
	assert.deepEqual(Array.from(p.field.vertexArrivalSeconds), [0, 200]);
	const a = [-30, 60] as const,
		b = [30, 60] as const,
		m = roadCoordinate(a, b, 0.5);
	assert.ok(m[1] > 60);
	assert.ok(
		Math.abs(sphericalDistance(a, m) * 2 - sphericalDistance(a, b)) < 1e-6,
	);
	assert.deepEqual(roadCoordinate(a, a, 0.3), a);
});

test("fixed-grid local budgets are monotone and coverage bits never act as seeds", () => {
	const g = grid(geography(), 10000),
		outputs: Uint16Array[] = [];
	for (const horizon of [100, 500, 1500]) {
		const times = new Uint16Array(g.count).fill(65535);
		times[0] = 0;
		g.parents.fill(255);
		setNibble(g.parents, 0, 9);
		setBit(g.coverage, g.count - 1);
		fillLocal(
			g.frame,
			times,
			g.parents,
			g.links,
			g.horizontal,
			g.diagonal,
			g.vertical,
			horizon,
			new DisplayQueue(new Uint32Array(10000), new Uint32Array(10000)),
			() => {},
		);
		outputs.push(times);
	}
	for (let k = 1; k < outputs.length; k++)
		for (let i = 0; i < g.count; i++)
			if (outputs[k - 1][i] !== 65535)
				assert.equal(outputs[k][i], outputs[k - 1][i]);
	assert.equal(outputs[0][g.count - 1], 65535);
	const masked = outputs[2].map((v) => (v !== 65535 ? 1 : 0));
	assert.ok(
		cellContours(
			Uint8Array.from(masked),
			g.frame.width,
			g.frame.height,
			-0.2,
			-0.2,
			0.01,
		).some((poly) => containsPolygon(center(g.frame, 0), poly)),
	);
});
