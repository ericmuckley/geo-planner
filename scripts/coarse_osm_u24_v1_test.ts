import assert from "node:assert/strict";
import test from "node:test";
import { MAX_UINT24, packUint24, Uint24View } from "./coarse_osm_u24_v1.ts";

test("independent little-endian golden bytes and full unsigned range", () => {
	const values = [0, 1, 255, 256, 65535, 65536, MAX_UINT24];
	const bytes = packUint24(values);
	assert.deepEqual(
		Array.from(bytes),
		[0, 0, 0, 1, 0, 0, 255, 0, 0, 0, 1, 0, 255, 255, 0, 0, 0, 1, 255, 255, 255],
	);
	const view = new Uint24View(bytes);
	assert.deepEqual(
		values.map((_, i) => view.at(i)),
		values,
	);
	assert.equal(view.byteLength, 3 * values.length);
});

test("seeded bit patterns preserve exact values without saturation", () => {
	let seed = 20261106;
	const values = Uint32Array.from({ length: 10000 }, () => {
		seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
		return seed >>> 8;
	});
	const view = new Uint24View(packUint24(values));
	for (let i = 0; i < values.length; i++) assert.equal(view.at(i), values[i]);
});

test("overflow, non-integers and invalid reads fail explicitly", () => {
	for (const value of [-1, MAX_UINT24 + 1, 0.5, NaN, Infinity]) {
		assert.throws(() => packUint24([value]), RangeError);
	}
	const view = new Uint24View(packUint24([1, 2]));
	for (const index of [-1, 2, 0.5, NaN, Infinity]) {
		assert.throws(() => view.at(index), RangeError);
	}
	for (const length of [1, 2, 4, 5]) {
		assert.throws(() => new Uint24View(new Uint8Array(length)), RangeError);
	}
	assert.throws(() => packUint24({ length: MAX_UINT24 + 2 }), RangeError);
});

test("subarrays share bytes and do not retain an expanded copy", () => {
	const bytes = packUint24([1, 2, 3]);
	const view = new Uint24View(bytes).subarray(1, 3);
	assert.equal(view.byteLength, 6);
	assert.equal(view.at(0), 2);
	bytes[3] = 42;
	assert.equal(view.at(0), 42);
	assert.equal(view.subarray(2).length, 0);
	assert.equal(new Uint24View(new Uint8Array()).length, 0);
	for (const [start, end] of [
		[-1, 1],
		[0, 3],
		[1, 0],
		[0.5, 1],
	]) {
		assert.throws(() => view.subarray(start, end), RangeError);
	}
});
