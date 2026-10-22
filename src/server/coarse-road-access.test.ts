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
	}
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
