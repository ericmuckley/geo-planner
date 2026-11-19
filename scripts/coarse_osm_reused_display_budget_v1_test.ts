import assert from "node:assert/strict";
import test from "node:test";
import {
	maximumReusedDisplayCells,
	reusedDisplayBytes,
} from "./coarse_osm_reused_display_budget_v1.ts";
import {
	CURVE_BYTES,
	DISPLAY_CAP_BYTES,
} from "./coarse_osm_split_display_budget_v1.ts";

test("reused views add no backing allocation and alter only query storage", () => {
	const input = {
		fieldPeakBytes: 20000,
		labelBytes: 8000,
		vertexBytes: 8000,
		maxWidth: 100,
		maxHeight: 80,
		heapEntries: 1000,
	};
	const labels = new ArrayBuffer(input.labelBytes);
	const vertices = new ArrayBuffer(input.vertexBytes);
	const otherField = new ArrayBuffer(
		input.fieldPeakBytes - labels.byteLength - vertices.byteLength,
	);
	const raster = new ArrayBuffer(2 * 1001 + 181);
	const curve = new ArrayBuffer(CURVE_BYTES);
	const cleanup = new ArrayBuffer(64);
	const sizes = reusedDisplayBytes(input, 1001);
	const masks = new Uint8Array(labels, 0, sizes.masks);
	const heap = new Uint32Array(vertices, 0, 2000);
	masks.fill(7);
	heap.fill(9);
	assert.equal(sizes.extraMasks, 0);
	assert.equal(sizes.extraQueue, 0);
	const buffers = new Set([
		labels,
		vertices,
		otherField,
		raster,
		curve,
		cleanup,
		masks.buffer,
		heap.buffer,
	]);
	assert.equal(
		[...buffers].reduce((n, b) => n + b.byteLength, 0),
		sizes.fill,
	);
	assert.equal(sizes.seed, sizes.fill);
});

test("small query workspaces budget full fallback allocations", () => {
	const input = {
		fieldPeakBytes: 10000,
		labelBytes: 40,
		vertexBytes: 20,
		maxWidth: 100,
		maxHeight: 80,
		heapEntries: 1000,
	};
	const sizes = reusedDisplayBytes(input, 1001);
	const masks = new ArrayBuffer(sizes.masks);
	const queue = new ArrayBuffer(8000);
	assert.equal(sizes.fill - sizes.seed, masks.byteLength + queue.byteLength);
});

test("capacity includes unreachable old buffers and cleanup without relying on GC", () => {
	const input = {
		fieldPeakBytes: 51032594,
		labelBytes: 4 * 9853365,
		vertexBytes: 2 * 5731903,
		maxWidth: 12002,
		maxHeight: 5102,
		heapEntries: 1000000,
	};
	const cells = maximumReusedDisplayCells(input);
	const fit = reusedDisplayBytes(input, cells);
	const over = reusedDisplayBytes(input, cells + 1);
	assert.ok(fit.seed <= DISPLAY_CAP_BYTES && fit.fill <= DISPLAY_CAP_BYTES);
	assert.ok(over.seed > DISPLAY_CAP_BYTES || over.fill > DISPLAY_CAP_BYTES);
	assert.throws(() =>
		maximumReusedDisplayCells({ ...input, fieldPeakBytes: 1000 }),
	);
});
