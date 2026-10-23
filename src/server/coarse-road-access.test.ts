import assert from "node:assert/strict";
import { test } from "node:test";
import { decodeGrid } from "./coarse-data.server";
import {
	distanceKm,
	estimateGrid,
	gridAttachments,
	gridPosition,
} from "./coarse-grid";
import v3 from "./data/coarse-grid-v3.json";
import data from "./data/coarse-grid-v4.json";

function rectangle(west: number, east: number, south = 0, north = 0.1) {
	return [
		[
			[west, south],
			[east, south],
			[east, north],
			[west, north],
			[west, south],
		],
	];
}

function fixture() {
	const bytes = (values: number[]) => Buffer.from(values).toString("base64");
	return {
		bounds: [0, 0, 0.1, 0.1],
		width: 1,
		height: 1,
		step: 0.1,
		localSpeedKph: 25,
		land: bytes([1]),
		traversable: bytes([1]),
		links: bytes([0, 0, 0, 0]),
		shoreLinks: bytes([0]),
		anchorOffsets: bytes([0, 0, 0, 0]),
		boundary: [rectangle(0, 0.1)],
		lakes: [] as number[][][][],
		roadVisits: [
			{
				cell: 0,
				speedKph: 80,
				anchorIndex: 2,
				offsets: [
					[-4000, -4000],
					[-4000, 0],
					[0, 0],
				],
			},
		],
	};
}

test("source attachment pays the road bend and seeds search with time rather than local-speed distance", () => {
	const grid = decodeGrid(fixture());
	const origin = { lon: 0.01, lat: 0.01 };
	const [attachment] = gridAttachments(grid, origin);
	const roadKm =
		distanceKm([0.01, 0.01], [0.01, 0.05]) +
		distanceKm([0.01, 0.05], [0.05, 0.05]);
	assert.ok(Math.abs(attachment.distanceKm - roadKm) < 1e-8);
	assert.equal(attachment.minutes, Math.ceil((roadKm / 80) * 36000) / 600);
	assert.ok(
		attachment.minutes > (distanceKm([0.01, 0.01], [0.05, 0.05]) / 80) * 60,
	);
	assert.ok(attachment.minutes < (attachment.distanceKm / 25) * 60);
	assert.equal(estimateGrid(grid, origin, 60).labels[0], attachment.minutes);
	const reversed = fixture();
	reversed.roadVisits[0].offsets.reverse();
	reversed.roadVisits[0].anchorIndex = 0;
	assert.deepEqual(gridAttachments(decodeGrid(reversed), origin), [attachment]);
});

test("off-road connection and along-road travel are both charged", () => {
	const grid = decodeGrid(fixture());
	const origin = { lon: 0.012, lat: 0.015 };
	const [attachment] = gridAttachments(grid, origin);
	assert.ok(attachment.roadKm && attachment.roadKm > 0);
	const localKm = attachment.distanceKm - attachment.roadKm;
	assert.ok(localKm > 0.2);
	assert.equal(
		attachment.minutes,
		Math.ceil((localKm / 25 + attachment.roadKm / 80) * 36000) / 600,
	);
	assert.ok(
		attachment.minutes >=
			(distanceKm([origin.lon, origin.lat], gridPosition(grid, 0)) / 80) * 60,
	);
});

test("road projection cannot cross a narrow water gap, but an explicit source-road leg can", () => {
	const raw = fixture();
	raw.lakes = [rectangle(0.04, 0.041)];
	raw.roadVisits[0] = {
		cell: 0,
		speedKph: 80,
		anchorIndex: 1,
		offsets: [
			[0, -4000],
			[0, 0],
		],
	};
	const origin = { lon: 0.01, lat: 0.01 };
	const grid = decodeGrid(raw);
	assert.deepEqual(gridAttachments(grid, origin), []);
	assert.equal(estimateGrid(grid, origin, 60).reachedCells, 1);
	raw.roadVisits[0] = {
		cell: 0,
		speedKph: 80,
		anchorIndex: 2,
		offsets: [
			[-4000, -4000],
			[0, -4000],
			[0, 0],
		],
	};
	const [bridge] = gridAttachments(decodeGrid(raw), origin);
	assert.ok(bridge.roadKm && bridge.minutes > 6);
});

test("an unrelated island cannot acquire a source-road attachment across its channel", () => {
	const raw = fixture();
	raw.boundary = [rectangle(0, 0.02), rectangle(0.04, 0.1)];
	raw.roadVisits[0] = {
		cell: 0,
		speedKph: 80,
		anchorIndex: 1,
		offsets: [
			[0, -4000],
			[0, 0],
		],
	};
	assert.deepEqual(
		gridAttachments(decodeGrid(raw), { lon: 0.01, lat: 0.01 }),
		[],
	);
});

test("road visits reject malformed anchors, speeds, duplicated cells and points", () => {
	for (const mutate of [
		(raw: ReturnType<typeof fixture>) => {
			raw.roadVisits[0].anchorIndex = 0;
		},
		(raw: ReturnType<typeof fixture>) => {
			raw.roadVisits[0].speedKph = 106;
		},
		(raw: ReturnType<typeof fixture>) => {
			raw.roadVisits.push(raw.roadVisits[0]);
		},
		(raw: ReturnType<typeof fixture>) => {
			raw.roadVisits[0].offsets.unshift(raw.roadVisits[0].offsets[0]);
			raw.roadVisits[0].anchorIndex++;
		},
	]) {
		const raw = fixture();
		mutate(raw);
		assert.throws(() => decodeGrid(raw), /road visit|Road visit/);
		assert.throws(
			() => decodeGrid({ ...raw, roadVisits: packed(raw.roadVisits) }),
			/road visit|Road visit/,
		);
	}
});

function packed(rows: ReturnType<typeof fixture>["roadVisits"]) {
	const cells = Buffer.alloc(rows.length * 4);
	const anchors = Buffer.alloc(rows.length * 4);
	const starts = Buffer.alloc((rows.length + 1) * 4);
	const offsets = Buffer.alloc(
		rows.reduce((sum, row) => sum + row.offsets.length * 4, 0),
	);
	let point = 0;
	for (const [i, row] of rows.entries()) {
		cells.writeUInt32LE(row.cell, i * 4);
		anchors.writeUInt32LE(row.anchorIndex, i * 4);
		starts.writeUInt32LE(point, i * 4);
		for (const p of row.offsets) {
			offsets.writeInt16LE(p[0], point * 4);
			offsets.writeInt16LE(p[1], point * 4 + 2);
			point++;
		}
	}
	starts.writeUInt32LE(point, rows.length * 4);
	return {
		encoding: "cell-visits-le-v1",
		cells: cells.toString("base64"),
		anchors: anchors.toString("base64"),
		starts: starts.toString("base64"),
		offsets: offsets.toString("base64"),
		speeds: Buffer.from(rows.map((r) => r.speedKph)).toString("base64"),
	};
}

test("packed visits preserve all v4 anchors, bends and cumulative distances exactly", () => {
	const visits = decodeGrid({
		...data,
		roadVisits: packed(data.roadVisits),
	}).roadVisits;
	const baseline = decodeGrid(data).roadVisits;
	assert.equal(visits?.size, baseline?.size);
	for (const [cell, visit] of visits ?? [])
		assert.deepEqual(visit, baseline?.get(cell));
});

test("packed visits materialize independent values without retaining query mutations", () => {
	const raw = fixture();
	const visits = decodeGrid({
		...raw,
		roadVisits: packed(raw.roadVisits),
	}).roadVisits;
	assert.ok(visits);
	const first = visits.get(0);
	assert.ok(first);
	const original = structuredClone(first);
	first.points[0][0] = 100;
	first.cumulativeKm[0] = 100;
	assert.deepEqual(visits.get(0), original);
	assert.deepEqual([...visits], [[0, original]]);
	for (const cell of [-1, 1, 0.5, Infinity, NaN])
		assert.equal(visits.get(cell), undefined);
});

test("packed visits reject truncated arrays, invalid ranges and unknown encoding", () => {
	for (const mutation of [
		{ cells: "" },
		{ anchors: "" },
		{ offsets: "AA==" },
		{ starts: Buffer.alloc(8).toString("base64") },
		{ encoding: "unknown" },
	]) {
		const raw = fixture();
		assert.throws(
			() =>
				decodeGrid({
					...raw,
					roadVisits: { ...packed(raw.roadVisits), ...mutation },
				}),
			/packed road visit/,
		);
	}
});

test("a supplemental road pays its land transfer to the fixed canonical anchor", () => {
	const raw = fixture();
	const supplemental = [
		{
			...raw.roadVisits[0],
			anchorIndex: 1,
			offsets: [
				[-4000, -4000],
				[-4000, 0],
			],
		},
	];
	raw.roadVisits = [];
	const grid = decodeGrid({
		...raw,
		supplementalRoadVisits: packed(supplemental),
	});
	const [attachment] = gridAttachments(grid, { lon: 0.01, lat: 0.01 });
	const transfer = distanceKm([0.01, 0.05], [0.05, 0.05]);
	const road = distanceKm([0.01, 0.01], [0.01, 0.05]);
	assert.ok(Math.abs(attachment.distanceKm - road - transfer) < 1e-8);
	assert.equal(
		attachment.minutes,
		Math.ceil((transfer / 25 + road / 80) * 36000) / 600,
	);
	raw.lakes = [rectangle(0.04, 0.041)];
	assert.throws(
		() => decodeGrid({ ...raw, supplementalRoadVisits: packed(supplemental) }),
		/transfer crosses/,
	);
});

test("all retained source visits own unchanged v3 anchors and satisfy physical-distance bounds", () => {
	for (const key of [
		"land",
		"traversable",
		"links",
		"roadDeciseconds",
		"displayLand",
		"anchorOffsets",
		"shoreLinks",
		"roadAccess",
		"roadSpeedsKph",
	] as const)
		assert.deepEqual(data[key], v3[key]);
	const grid = decodeGrid(data);
	assert.equal(grid.roadVisits?.size, data.roadVisits.length);
	let points = 0;
	for (const [cell, visit] of grid.roadVisits ?? []) {
		const anchor = gridPosition(grid, cell);
		assert.ok(distanceKm(anchor, visit.points[visit.anchorIndex]) < 1e-7);
		for (let i = 0; i < visit.points.length; i++) {
			const arc = Math.abs(
				visit.cumulativeKm[i] - visit.cumulativeKm[visit.anchorIndex],
			);
			assert.ok(arc + 1e-7 >= distanceKm(anchor, visit.points[i]));
			points++;
		}
		// Sample arbitrary source vertices throughout the dataset, not just named
		// regional cases. Every returned attachment must pay physical travel time.
		if (cell % 149 !== 0) continue;
		const point = visit.points[0];
		for (const attachment of gridAttachments(grid, {
			lon: point[0],
			lat: point[1],
		})) {
			assert.ok(
				attachment.minutes + 1e-7 >=
					(distanceKm(point, gridPosition(grid, attachment.cell)) / 105) * 60,
			);
			assert.ok(
				attachment.distanceKm + 1e-7 >=
					distanceKm(point, gridPosition(grid, attachment.cell)),
			);
		}
	}
	assert.equal(
		points,
		data.roadVisits.reduce((sum, v) => sum + v.offsets.length, 0),
	);
});
