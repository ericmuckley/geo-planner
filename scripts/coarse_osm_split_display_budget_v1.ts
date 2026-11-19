/** Capacity for road seeding followed by a separately owned local raster phase. */
export const DISPLAY_CAP_BYTES = 67108864;
export const CURVE_BYTES = 12 * 4096;

export type SplitDisplayBudget = {
	fieldPeakBytes: number;
	maxWidth: number;
	maxHeight: number;
	heapEntries: number;
};

function validate(input: SplitDisplayBudget) {
	for (const value of Object.values(input))
		if (!Number.isSafeInteger(value) || value < 1)
			throw new Error("Split display budget integer domain");
	if (input.fieldPeakBytes >= DISPLAY_CAP_BYTES || input.heapEntries > 1000000)
		throw new Error("Split display budget capacity domain");
}

export function splitDisplayBytes(input: SplitDisplayBudget, cells: number) {
	validate(input);
	if (!Number.isSafeInteger(cells) || cells < 1)
		throw new Error("Split display cell domain");
	const raster = 2 * cells + input.maxWidth + input.maxHeight + 1;
	return {
		seed: input.fieldPeakBytes + raster + CURVE_BYTES,
		fill:
			raster +
			4 * Math.ceil(cells / 8) +
			2 * Math.ceil(cells / 2) +
			2 * input.maxWidth +
			4 * input.maxHeight +
			8 * input.heapEntries,
	};
}

export function maximumSplitDisplayCells(input: SplitDisplayBudget) {
	validate(input);
	let low = 0;
	let high = Math.max(
		0,
		Math.floor(
			(DISPLAY_CAP_BYTES -
				input.fieldPeakBytes -
				input.maxWidth -
				input.maxHeight -
				1 -
				CURVE_BYTES) /
				2,
		),
	);
	while (low < high) {
		const middle = Math.ceil((low + high) / 2);
		const bytes = splitDisplayBytes(input, middle);
		if (bytes.seed <= DISPLAY_CAP_BYTES && bytes.fill <= DISPLAY_CAP_BYTES)
			low = middle;
		else high = middle - 1;
	}
	if (!low) throw new Error("No split display capacity");
	return low;
}
