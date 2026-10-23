import assert from "node:assert/strict";
import test from "node:test";
import { gzipSync } from "node:zlib";
import { decodeGrid } from "./coarse-data.server";
import {
	distanceKm,
	estimateGrid,
	gridAttachments,
	gridCellMinutes,
	gridPosition,
	gridTransitions,
} from "./coarse-grid";

const bytes = (values: Uint8Array | Uint16Array | Int16Array | Uint32Array) =>
	Buffer.from(values.buffer, values.byteOffset, values.byteLength).toString(
		"base64",
	);
function fixture() {
	const anchors = new Int16Array([-4000, 0, -4000, 0, -4000, 0]);
	const positions = new Int16Array([4000, 0, 4000, 0, 4000, 0]);
	const transfers = new Uint16Array(3),
		roads = new Uint16Array(12),
		oldRoads = new Uint16Array(12);
	for (let cell = 0; cell < 3; cell++)
		transfers[cell] = Math.max(
			1,
			Math.ceil(
				(distanceKm(
					[0.05 + cell * 0.1 + 0.04, 0.05],
					[0.05 + cell * 0.1 - 0.04, 0.05],
				) /
					25) *
					36000,
			),
		);
	for (let cell = 0; cell < 2; cell++) {
		roads[cell * 4] = Math.ceil(
			(distanceKm([0.09 + cell * 0.1, 0.05], [0.19 + cell * 0.1, 0.05]) / 80) *
				36000,
		);
		oldRoads[cell * 4] = Math.ceil(
			(distanceKm([0.09 + cell * 0.1, 0.05], [0.19 + cell * 0.1, 0.05]) / 80 +
				(distanceKm([0.09, 0.05], [0.01, 0.05]) * 2) / 25) *
				36000,
		);
	}
	return {
		bounds: [0, 0, 0.3, 0.1],
		width: 3,
		height: 1,
		step: 0.1,
		localSpeedKph: 25,
		land: bytes(new Uint8Array([1, 1, 1])),
		traversable: bytes(new Uint8Array([1, 1, 1])),
		links: bytes(new Uint8Array([80, 0, 0, 0, 80, 0, 0, 0, 0, 0, 0, 0])),
		anchorOffsets: bytes(anchors),
		roadDeciseconds: bytes(oldRoads),
		shoreLinks: bytes(new Uint8Array(3)),
		boundary: [
			[
				[
					[0, 0],
					[0.3, 0],
					[0.3, 0.1],
					[0, 0.1],
					[0, 0],
				],
			],
		],
		lakes: [] as number[][][][],
		supplementalRoadVisits: Array.from({ length: 3 }, (_, cell) => ({
			cell,
			speedKph: 80,
			anchorIndex: 1,
			offsets: [
				[3000, 0],
				[4000, 0],
				[4900, 0],
			],
		})),
		roadLayer: {
			encoding: "census-road-layer-le-v1",
			anchorOffsets: bytes(positions),
			roadDeciseconds: bytes(roads),
			transferDeciseconds: bytes(transfers),
		},
	};
}

test("compressed arrays preserve graph costs, source access and contours", () => {
	const raw = fixture();
	const data = {
		...raw,
		supplementalRoadVisits: {
			encoding: "cell-visits-le-v1",
			cells: bytes(new Uint32Array([0, 1, 2])),
			speeds: bytes(new Uint8Array([80, 80, 80])),
			anchors: bytes(new Uint32Array([1, 1, 1])),
			starts: bytes(new Uint32Array([0, 3, 6, 9])),
			offsets: bytes(
				new Int16Array(
					raw.supplementalRoadVisits.flatMap((v) => v.offsets.flat()),
				),
			),
		},
	};
	const original = decodeGrid(data);
	const compress = (value: string) =>
		`gzip:${gzipSync(Buffer.from(value, "base64")).toString("base64")}`;
	for (const key of [
		"land",
		"traversable",
		"links",
		"anchorOffsets",
		"roadDeciseconds",
		"shoreLinks",
	] as const)
		data[key] = compress(data[key]);
	for (const key of [
		"cells",
		"speeds",
		"anchors",
		"starts",
		"offsets",
	] as const)
		data.supplementalRoadVisits[key] = compress(
			data.supplementalRoadVisits[key],
		);
	for (const key of [
		"anchorOffsets",
		"roadDeciseconds",
		"transferDeciseconds",
	] as const)
		data.roadLayer[key] = compress(data.roadLayer[key]);
	const packed = decodeGrid(data);
	const origin = { lon: 0.09, lat: 0.05 };
	assert.deepEqual(
		gridAttachments(packed, origin),
		gridAttachments(original, origin),
	);
	const before = estimateGrid(original, origin, 20),
		after = estimateGrid(packed, origin, 20);
	assert.deepEqual(after.labels, before.labels);
	assert.deepEqual(after.coordinates, before.coordinates);
	assert.equal(after.reachedCells, before.reachedCells);
	data.land = "gzip:bm90LWd6aXA=";
	assert.throws(() => decodeGrid(data));
});

test("a continuous road pays transfers when switching states, not in every cell", () => {
	const raw = fixture(),
		grid = decodeGrid(raw);
	const baseline = decodeGrid({ ...raw, roadLayer: undefined });
	const origin = { lon: 0.09, lat: 0.05 };
	const next = estimateGrid(grid, origin, 20),
		old = estimateGrid(baseline, origin, 120);
	assert.ok(next.labels[5] < 17);
	assert.equal(next.labels[2], Infinity);
	assert.equal(next.reachedCells, 3);
	assert.equal(gridCellMinutes(grid, next.labels, 2), next.labels[5]);
	assert.ok(old.labels[2] > 60);
	const transfer = [...gridTransitions(grid, 5)].find(
		(e) => e.kind === "transfer",
	);
	assert.ok(transfer);
	assert.equal(transfer.target, 2);
	assert.equal(
		transfer.minutes,
		(grid.roadLayer?.transferDeciseconds[2] ?? 0) / 600,
	);
	assert.ok(transfer.minutes > 21);
	const reverse = estimateGrid(grid, { lon: 0.29, lat: 0.05 }, 20);
	assert.ok(Math.abs(reverse.labels[3] - next.labels[5]) < 1e-8);
});

test("all legacy attachment and route options remain available alongside the road state", () => {
	const raw = fixture(),
		grid = decodeGrid(raw),
		old = decodeGrid({ ...raw, roadLayer: undefined });
	const origin = { lon: 0.07, lat: 0.05 };
	const attachments = gridAttachments(grid, origin),
		previous = gridAttachments(old, origin);
	for (const entry of previous)
		assert.deepEqual(
			attachments.find((a) => a.cell === entry.cell),
			entry,
		);
	assert.ok(attachments.some((a) => a.cell >= 3));
	const before = estimateGrid(old, origin, 120),
		after = estimateGrid(grid, origin, 120);
	for (let cell = 0; cell < 3; cell++)
		assert.ok(after.labels[cell] <= before.labels[cell] + 1e-8);
	assert.deepEqual(gridPosition(grid, 4), [0.05 + 1 * 0.1 + 0.04, 0.05]);
});

test("road states acquire no implicit overland links", () => {
	const raw = fixture();
	raw.roadLayer.roadDeciseconds = bytes(new Uint16Array(12));
	const grid = decodeGrid(raw),
		size = grid.width * grid.height;
	const edges = [...gridTransitions(grid, size)];
	assert.equal(edges.length, 1);
	assert.equal(edges[0].kind, "transfer");
	assert.ok(edges[0].minutes > 0);
});

test("road-layer data rejects undercharged transfers, changed anchors and dangling links", () => {
	for (const kind of ["transfer", "anchor", "link", "length", "encoding"]) {
		const raw = fixture();
		if (kind === "transfer")
			raw.roadLayer.transferDeciseconds = bytes(new Uint16Array([1, 1, 1]));
		if (kind === "anchor")
			raw.roadLayer.anchorOffsets = bytes(new Int16Array(6));
		if (kind === "link") {
			const roads = new Uint16Array(12);
			roads[3] = 1;
			raw.roadLayer.roadDeciseconds = bytes(roads);
		}
		if (kind === "length") raw.roadLayer.roadDeciseconds = "";
		if (kind === "encoding") raw.roadLayer.encoding = "unknown";
		assert.throws(
			() => decodeGrid(raw),
			kind === "length"
				? /Invalid grid word array length/
				: /Road layer|road layer/,
		);
	}
	const water = fixture();
	water.lakes = [
		[
			[
				[0.04, 0],
				[0.06, 0],
				[0.06, 0.1],
				[0.04, 0.1],
				[0.04, 0],
			],
		],
	];
	assert.throws(() => decodeGrid(water), /transfer crosses water/);
});
