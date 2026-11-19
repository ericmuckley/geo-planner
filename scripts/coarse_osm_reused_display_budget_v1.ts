/** Reuse query-label storage for masks and vertex storage for the local queue. */
import {
	CURVE_BYTES,
	DISPLAY_CAP_BYTES,
	type SplitDisplayBudget,
	splitDisplayBytes,
} from "./coarse_osm_split_display_budget_v1.ts";

export type ReusedDisplayBudget = SplitDisplayBudget & {
	labelBytes: number;
	vertexBytes: number;
};

export function reusedDisplayBytes(input: ReusedDisplayBudget, cells: number) {
	// Retain the existing domain checks and count every old allocation even before GC.
	splitDisplayBytes(input, cells);
	if (input.labelBytes + input.vertexBytes > input.fieldPeakBytes)
		throw new Error("Query workspace backing exceeds declared field peak");
	const raster = 2 * cells + input.maxWidth + input.maxHeight + 1;
	const masks =
		4 * Math.ceil(cells / 8) +
		2 * Math.ceil(cells / 2) +
		2 * input.maxWidth +
		4 * input.maxHeight;
	const extraMasks = input.labelBytes >= masks ? 0 : masks;
	const extraQueue =
		input.vertexBytes >= 8 * input.heapEntries ? 0 : 8 * input.heapEntries;
	// The sealed field allocator creates one 64-byte seed placeholder during cleanup.
	const seed = input.fieldPeakBytes + raster + CURVE_BYTES + 64;
	return {
		seed,
		fill: seed + extraMasks + extraQueue,
		masks,
		extraMasks,
		extraQueue,
	};
}

export function maximumReusedDisplayCells(input: ReusedDisplayBudget) {
	reusedDisplayBytes(input, 1);
	let low = 0;
	let high = Math.max(
		0,
		Math.floor(
			(DISPLAY_CAP_BYTES -
				input.fieldPeakBytes -
				input.maxWidth -
				input.maxHeight -
				1 -
				CURVE_BYTES -
				64) /
				2,
		),
	);
	while (low < high) {
		const middle = Math.ceil((low + high) / 2);
		const bytes = reusedDisplayBytes(input, middle);
		if (bytes.seed <= DISPLAY_CAP_BYTES && bytes.fill <= DISPLAY_CAP_BYTES)
			low = middle;
		else high = middle - 1;
	}
	if (!low) throw new Error("No reused display capacity");
	return low;
}
