import assert from "node:assert/strict";
import test from "node:test";
import {
	elevationMatches,
	gridHeight,
	gridPixel,
	gridWidth,
	pixelLocation,
} from "../lib/area-layers";

test("area pixels preserve the Web Mercator grid and return to the same map coordinates", () => {
	const [lon, lat] = pixelLocation(gridWidth, gridHeight);
	const [column, row] = gridPixel(lon, lat);
	assert.ok(Math.abs(column - gridWidth) < 1e-8);
	assert.ok(Math.abs(row - gridHeight) < 1e-8);
	assert.ok(lon > -66);
	assert.ok(lat < 24);
	const [x, y] = gridPixel(-105, 39.5);
	const [recoveredLon, recoveredLat] = pixelLocation(x, y);
	assert.ok(Math.abs(recoveredLon + 105) < 1e-8);
	assert.ok(Math.abs(recoveredLat - 39.5) < 1e-8);
});

test("elevation includes both exact endpoints and excludes missing or out-of-range data", () => {
	assert.equal(elevationMatches(32768 + 1524, [5000, 10000]), true);
	assert.equal(elevationMatches(32768 + 1523, [5000, 10000]), false);
	assert.equal(elevationMatches(32768 + 3048, [5000, 10000]), true);
	assert.equal(elevationMatches(32768 + 3049, [5000, 10000]), false);
	assert.equal(elevationMatches(32768 - 1, [0, 10000]), false);
	assert.equal(elevationMatches(32768, [0, 10000]), true);
	assert.equal(elevationMatches(0, [0, 10000]), false);
});
