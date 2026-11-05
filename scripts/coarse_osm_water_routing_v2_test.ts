import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { gzipSync } from "node:zlib";
import { landConnection as coarseConnection } from "../src/server/coarse-geography.ts";
import { diagnosticAccessFilledDisplay as oldDisplay } from "./coarse_osm_access_display_v1.ts";
import { diagnosticAccessFilledDisplay } from "./coarse_osm_access_display_v2.ts";
import {
	geography,
	prepared,
	rectangle,
} from "./coarse_osm_access_fixture_v2.ts";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import { computeDiagnosticAccessRoadField } from "./coarse_osm_access_road_field_v2.ts";
import { accessDisplayPointTiming } from "./coarse_osm_access_timing_v2.ts";
import * as oldGrid from "./coarse_osm_display_grid_v1.ts";
import { rasterLand, rasterLinks } from "./coarse_osm_display_grid_v2.ts";
import { displayPointWitness } from "./coarse_osm_local_witness_v2.ts";
import { connectOriginAccessV3 } from "./coarse_osm_origin_access_v3.ts";
import { connectOriginAccessV4 } from "./coarse_osm_origin_access_v4.ts";
import { connectorPrice } from "./coarse_osm_origin_connections_v1.ts";
import {
	landConnection,
	legacyRoutingGeography,
	waterRoutingGeography as unindexedWaterGeography,
} from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV2 as waterRoutingGeography } from "./coarse_osm_routing_geography_v2.ts";
import {
	createSeedTrace,
	offlineTraceAccessDisplay,
} from "./coarse_osm_trace_display_v2.ts";
import { loadWaterRaster } from "./coarse_osm_water_raster_loader_v1.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";

const sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");

async function packet(
	water: (x: number, y: number) => boolean = () => false,
	uncertain: (x: number, y: number) => boolean = () => false,
	grid = { xE7: -1000000, yE7: -1000000, stepE7: 50000, columns: 40, rows: 40 },
) {
	const root = await mkdtemp(path.join(os.tmpdir(), "geo-water-adapter-"));
	try {
		const cells = grid.columns * grid.rows;
		const plane = async (name: string, selected: typeof water) => {
			const raw = Buffer.alloc(Math.ceil(cells / 8));
			let set = 0;
			for (let y = 0; y < grid.rows; y++)
				for (let x = 0; x < grid.columns; x++)
					if (selected(x, y)) {
						const i = y * grid.columns + x;
						raw[i >>> 3] |= 1 << (i % 8);
						set++;
					}
			const compressed = gzipSync(raw);
			await writeFile(path.join(root, `${name}.bits.gz`), compressed);
			return {
				file: `${name}.bits.gz`,
				rawFile: `${name}.bits`,
				rawBytes: raw.length,
				rawSha256: sha(raw),
				compressedBytes: compressed.length,
				compressedSha256: sha(compressed),
				setCells: set,
			};
		};
		const manifest = {
			format: "exact-water-centers-and-source-uncertainty-v1",
			grid: { ...grid, cells, bitOrder: "row-major-lsb-first" },
			planes: {
				water: await plane("water-center", water),
				uncertainty: await plane("source-uncertainty", uncertain),
			},
			sourceCounts: {
				features: 0,
				rings: 0,
				points: 0,
				excludedFeatures: 0,
				knownExcludedBounds: 0,
			},
			sourceIncompleteFeatures: [],
			sourceGeometryCompletelyBounded: true,
			semantics: "Synthetic routing adapter fixture only.",
		};
		const encoded = Buffer.from(JSON.stringify(manifest));
		await writeFile(path.join(root, "manifest.json"), encoded);
		const pin = sha(encoded);
		return {
			current: await loadWaterRasterV2(root, pin),
			old: await loadWaterRaster(root, pin),
		};
	} finally {
		await rm(root, { recursive: true, force: true });
	}
}

test("V2 cell flags and every closed rectangle agree with independent bit iteration", async () => {
	const g = { xE7: -120, yE7: -110, stepE7: 17, columns: 5, rows: 3 };
	const wet = (x: number, y: number) => (x + y) % 3 === 0,
		unknown = (x: number, y: number) => (x + y * 3) % 4 === 0;
	const { current, old } = await packet(wet, unknown, g);
	assert.equal(current.backingBytes, old.backingBytes);
	assert.deepEqual(current.planeFingerprints, old.planeFingerprints);
	for (let y = -1; y <= g.rows; y++)
		for (let x = -1; x <= g.columns; x++) {
			assert.equal(
				current.cellFlags(x, y),
				x < 0 || y < 0 || x >= g.columns || y >= g.rows
					? null
					: Number(wet(x, y)) + 2 * Number(unknown(x, y)),
			);
			const point = [
				(g.xE7 + (x + 0.5) * g.stepE7) / 1e7,
				(g.yE7 + (y + 0.5) * g.stepE7) / 1e7,
			] as const;
			assert.deepEqual(current.lookup(point), old.lookup(point));
		}
	const xs = [
		g.xE7 - 1,
		g.xE7,
		g.xE7 + 1,
		g.xE7 + 16,
		g.xE7 + 17,
		g.xE7 + 18,
		g.xE7 + 50,
		g.xE7 + 84,
		g.xE7 + 85,
	];
	const ys = [
		g.yE7 - 1,
		g.yE7,
		g.yE7 + 1,
		g.yE7 + 16,
		g.yE7 + 17,
		g.yE7 + 18,
		g.yE7 + 49,
		g.yE7 + 50,
		g.yE7 + 51,
	];
	for (const x1 of xs)
		for (const x2 of xs)
			for (const y1 of ys)
				for (const y2 of ys) {
					if (x1 > x2 || y1 > y2) continue;
					let expected =
						x1 <= g.xE7 ||
						y1 <= g.yE7 ||
						x2 >= g.xE7 + g.columns * g.stepE7 ||
						y2 >= g.yE7 + g.rows * g.stepE7;
					for (let row = 0; row < g.rows; row++)
						for (let col = 0; col < g.columns; col++)
							if (unknown(col, row)) {
								const left = g.xE7 + col * g.stepE7,
									bottom = g.yE7 + row * g.stepE7;
								expected ||=
									left <= x2 &&
									left + g.stepE7 >= x1 &&
									bottom <= y2 &&
									bottom + g.stepE7 >= y1;
							}
					assert.equal(
						current.uncertaintyTouchesE7Box(x1, y1, x2, y2),
						expected,
					);
				}
});

test("origin and every initial choice preserve legacy math and work counts", () => {
	const p = prepared(
		[
			[0.0004, -0.001],
			[0.0004, 0.001],
			[-0.004, -0.001],
			[-0.004, 0.001],
		],
		[
			[0, 1],
			[2, 3],
		],
	);
	for (const geo of [
		geography(),
		geography([[rectangle(0.0001, -0.01, 0.0003, 0.01)]]),
		{ ...geography(), boundary: [[rectangle(0.01, -0.01, 0.02, 0.01)]] },
	]) {
		const old = connectOriginAccessV3(
			p.graph,
			p.geometry,
			p.keys,
			p.starts,
			geo,
			[0, 0],
		);
		const current = connectOriginAccessV4(
			p.graph,
			p.geometry,
			p.keys,
			p.starts,
			legacyRoutingGeography(geo),
			[0, 0],
		);
		assert.deepEqual(current, old);
	}
});

test("fine geography permits paid land access beyond the unchanged off-mask allowance", async () => {
	const p = prepared(
			[
				[0.004, -0.01],
				[0.004, 0.01],
			],
			[[0, 1]],
		),
		geo = geography([[rectangle(-0.01, -0.01, 0.01, 0.01)]]);
	assert.equal(
		connectOriginAccessV3(p.graph, p.geometry, p.keys, p.starts, geo, [0, 0])
			.primary,
		null,
	);
	const current = connectOriginAccessV4(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		waterRoutingGeography(geo, (await packet()).current),
		[0, 0],
	);
	assert.ok(
		current.primary &&
			current.primary.connectorMeters > 100 &&
			current.primary.connectorTicks > 0,
	);
	assert.equal(current.maskOmissionAllowance, false);
	assert.equal(current.primary.kind, "land-connector");
	for (const c of current.connections)
		assert.equal(
			c.connectorTicks,
			connectorPrice(c.origin, c.snap.coordinate).ticks,
		);
});

test("one-meter modeled road and paid100m initial off-mask rules remain unchanged", async () => {
	const geo = geography();
	geo.boundary = [[rectangle(0.01, -0.01, 0.02, 0.01)]];
	const routing = waterRoutingGeography(geo, (await packet()).current);
	for (const [x, supported] of [
		[0, true],
		[0.0004, true],
		[0.002, false],
	] as const) {
		const p = prepared(
			[
				[x, -0.001],
				[x, 0.001],
			],
			[[0, 1]],
		);
		const result = connectOriginAccessV4(
			p.graph,
			p.geometry,
			p.keys,
			p.starts,
			routing,
			[0, 0],
		);
		assert.equal(Boolean(result.primary), supported);
		for (const c of result.connections) assert.ok(c.connectorMeters <= 100);
	}
});

test("legacy raster cells, boundaries and every link stay byte-identical", () => {
	const geo = geography([[rectangle(-0.01, -0.02, 0.01, 0.02)]]),
		routing = legacyRoutingGeography(geo);
	for (const step of [5000, 7234, 25000]) {
		const frame = oldGrid.makeFrame([-0.04, -0.03, 0.04, 0.03], step),
			n = frame.width * frame.height;
		const make = () => ({
			land: new Uint8Array(Math.ceil(n / 8)),
			boundary: new Uint8Array(Math.ceil(n / 8)),
			links: new Uint8Array(Math.ceil(n / 2)),
			row: new Uint8Array(2 * frame.width),
		});
		const a = make(),
			b = make();
		oldGrid.rasterLand(frame, geo, a.land, a.boundary, a.row, () => {});
		rasterLand(frame, routing, b.land, b.boundary, b.row, () => {});
		oldGrid.rasterLinks(frame, geo, a.land, a.boundary, a.links, () => {});
		rasterLinks(frame, routing, b.land, b.boundary, b.links, () => {});
		assert.deepEqual(b, a);
	}
});

test("water raster centers and every shortcut/link agree with the same continuous policy", async () => {
	const wet = (x: number) => x === 21 || x === 22;
	const p = (await packet(wet, (x) => x >= 20 && x <= 23)).current;
	const geo = waterRoutingGeography(
		geography([[rectangle(-0.008, -0.01, 0.008, 0.01)]]),
		p,
	);
	for (const step of [5000, 7234, 25000]) {
		const frame = oldGrid.makeFrame([-0.03, -0.02, 0.04, 0.03], step),
			n = frame.width * frame.height;
		const land = new Uint8Array(Math.ceil(n / 8)),
			boundary = new Uint8Array(Math.ceil(n / 8)),
			links = new Uint8Array(Math.ceil(n / 2));
		rasterLand(
			frame,
			geo,
			land,
			boundary,
			new Uint8Array(2 * frame.width),
			() => {},
		);
		rasterLinks(frame, geo, land, boundary, links, () => {});
		for (let y = 0; y < frame.height; y++)
			for (let x = 0; x < frame.width; x++) {
				const i = y * frame.width + x,
					a = oldGrid.center(frame, i);
				assert.equal(Boolean(oldGrid.bit(land, i)), landConnection(geo, a, a));
				for (let d = 0; d < 4; d++) {
					const [dx, dy] = oldGrid.DIRECTIONS[d],
						nx = x + dx,
						ny = y + dy;
					if (nx < 0 || nx >= frame.width || ny >= frame.height) continue;
					const j = ny * frame.width + nx,
						b = oldGrid.center(frame, j);
					assert.equal(
						oldGrid.hasLink(links, i, j, d),
						Boolean(oldGrid.bit(land, i) && oldGrid.bit(land, j)) &&
							landConnection(geo, a, b),
					);
				}
			}
	}
});

test("legacy output, restored field and scratch remain identical through adapters", () => {
	const p = prepared(
			[
				[0, 0],
				[0.03, 0],
			],
			[[0, 1]],
		),
		geo = geography(),
		routing = legacyRoutingGeography(geo),
		origin = [0, 0.0001] as const;
	const access = connectOriginAccessV4(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		routing,
		origin,
	);
	assert.ok(access.primary);
	const field = computeDiagnosticAccessRoadField(
		p.graph,
		p.geometry,
		accessStarts(access.primary, access.connections),
		{ maxTicks: 12000, maxHeapEntries: 256 },
	);
	const before = field.vertexArrivalSeconds.slice(),
		options = { maxCells: 10000, heapEntries: 1000 };
	const old = oldDisplay(
			p.graph,
			p.geometry,
			geo,
			access.primary,
			field,
			options,
		),
		current = diagnosticAccessFilledDisplay(
			p.graph,
			p.geometry,
			routing,
			access.primary,
			field,
			options,
		);
	assert.deepEqual(current.output, old.output);
	assert.deepEqual(field.vertexArrivalSeconds, before);
	assert.equal(
		current.stats.maximumBackingBufferBytes,
		old.stats.maximumBackingBufferBytes,
	);
	assert.ok(current.stats.maximumBackingBufferBytes < 67108864);
});

test("trace, terminal timing and independent suffix replay use the refined policy", async () => {
	const p = prepared(
			[
				[0, 0],
				[0.03, 0],
			],
			[[0, 1]],
		),
		origin = [0, 0.0001] as const;
	const geo = waterRoutingGeography(
		geography([[rectangle(-0.01, -0.01, 0.01, 0.01)]]),
		(await packet()).current,
	);
	const access = connectOriginAccessV4(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		geo,
		origin,
	);
	assert.ok(access.primary);
	const field = computeDiagnosticAccessRoadField(
			p.graph,
			p.geometry,
			accessStarts(access.primary, access.connections),
			{ maxTicks: 12000, maxHeapEntries: 256 },
		),
		trace = createSeedTrace(10000);
	let checked = false;
	offlineTraceAccessDisplay(p.graph, p.geometry, geo, access.primary, field, {
		seedTrace: trace,
		maxCells: 10000,
		heapEntries: 1000,
		probe: (grid) => {
			const target = [0.0325, 0.0025] as const;
			const witness = displayPointWitness(
				p.graph,
				p.geometry,
				geo,
				field,
				grid,
				trace,
				origin,
				target,
				null,
			);
			assert.deepEqual(
				witness.measured,
				accessDisplayPointTiming(
					p.graph,
					p.geometry,
					geo,
					field,
					grid,
					origin,
					target,
					null,
				),
			);
			assert.equal(witness.measured.kind, "local-grid");
			assert.ok(
				witness.measured.ticks !== null && witness.coordinates.length >= 3,
			);
			assert.equal(
				(witness.fieldRoadTicks ?? 0) +
					Object.values(witness.components).reduce((a, b) => a + b, 0),
				witness.measured.ticks,
			);
			for (let i = 1; i < witness.coordinates.length; i++)
				assert.ok(
					landConnection(
						geo,
						[...witness.coordinates[i - 1]],
						[...witness.coordinates[i]],
					),
				);
			checked = true;
		},
	});
	assert.ok(checked);
});

test("missing policy and existing capacity guards fail rather than silently use old geography", async () => {
	assert.throws(() => landConnection(geography() as never, [0, 0], [0, 0]));
	const p = prepared(
			[
				[0, 0],
				[0.004, 0],
				[0, 0.004],
			],
			[
				[0, 1],
				[0, 2],
			],
		),
		geo = waterRoutingGeography(geography(), (await packet()).current);
	assert.throws(() =>
		connectOriginAccessV4(
			p.graph,
			p.geometry,
			p.keys,
			p.starts,
			geo,
			[0, 0],
			() => {},
			0,
		),
	);
	assert.throws(() => createSeedTrace(2500001));
});

test("index correction preserves unindexed fallback and frozen fine policy", async () => {
	const source = geography();
	source.lakes = [[rectangle(-0.025, -0.035, 0.035, 0.025)]];
	const mask = (
		await packet(
			(x, y) => x > 16 && x < 22 && y > 16 && y < 22,
			(x, y) => (x + y) % 3 === 0,
		)
	).current;
	const old = unindexedWaterGeography(source, mask),
		indexed = waterRoutingGeography(source, mask);
	let seed = 39483;
	const value = () => {
		seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
		return (seed / 2 ** 32 - 0.5) * 0.24;
	};
	for (let i = 0; i < 4096; i++) {
		const a = [value(), value()],
			b = [value(), value()];
		assert.equal(coarseConnection(old, a, a), coarseConnection(indexed, a, a));
		for (const prefix of [0, 0.1, 1])
			assert.equal(
				landConnection(old, a, b, prefix),
				landConnection(indexed, a, b, prefix),
			);
	}
});
