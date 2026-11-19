import assert from "node:assert/strict";
import test from "node:test";
import {
	CURVE_BYTES,
	DISPLAY_CAP_BYTES,
	maximumSplitDisplayCells,
	splitDisplayBytes,
} from "./coarse_osm_split_display_budget_v1.ts";

test("phase accounting matches independent actual buffer allocations", () => {
	const input = {
		fieldPeakBytes: 100000,
		maxWidth: 100,
		maxHeight: 80,
		heapEntries: 500,
	};
	const cells = 1001;
	const raster = new ArrayBuffer(2 * cells + 181);
	const field = new ArrayBuffer(input.fieldPeakBytes);
	const curve = new ArrayBuffer(CURVE_BYTES);
	const land = Array.from(
		{ length: 4 },
		() => new Uint8Array(Math.ceil(cells / 8)),
	);
	const nibbles = Array.from(
		{ length: 2 },
		() => new Uint8Array(Math.ceil(cells / 2)),
	);
	const row = new Uint8Array(2 * input.maxWidth);
	const horizontal = new Uint16Array(input.maxHeight);
	const diagonal = new Uint16Array(input.maxHeight);
	const heap = new ArrayBuffer(8 * input.heapEntries);
	const measured = splitDisplayBytes(input, cells);
	assert.equal(
		measured.seed,
		field.byteLength + raster.byteLength + curve.byteLength,
	);
	assert.equal(
		measured.fill,
		raster.byteLength +
			[...land, ...nibbles, row, horizontal, diagonal].reduce(
				(sum, view) => sum + view.byteLength,
				0,
			) +
			heap.byteLength,
	);
});

test("the maximum fits both phases and the next cell exceeds a phase", () => {
	for (const fieldPeakBytes of [100000, 51032594, DISPLAY_CAP_BYTES - 100000]) {
		const input = {
			fieldPeakBytes,
			maxWidth: 12002,
			maxHeight: 5102,
			heapEntries: 1000000,
		};
		const cells = maximumSplitDisplayCells(input);
		const fit = splitDisplayBytes(input, cells);
		const over = splitDisplayBytes(input, cells + 1);
		assert.ok(fit.seed <= DISPLAY_CAP_BYTES && fit.fill <= DISPLAY_CAP_BYTES);
		assert.ok(over.seed > DISPLAY_CAP_BYTES || over.fill > DISPLAY_CAP_BYTES);
	}
});

test("invalid or exhausted allocations refuse before any producer", () => {
	for (const fieldPeakBytes of [
		0,
		-1,
		0.5,
		NaN,
		DISPLAY_CAP_BYTES,
		DISPLAY_CAP_BYTES - 1,
	])
		assert.throws(() =>
			maximumSplitDisplayCells({
				fieldPeakBytes,
				maxWidth: 100,
				maxHeight: 100,
				heapEntries: 1000000,
			}),
		);
	assert.throws(() =>
		maximumSplitDisplayCells({
			fieldPeakBytes: 100,
			maxWidth: 100,
			maxHeight: 100,
			heapEntries: 1000001,
		}),
	);
});
