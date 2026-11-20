import assert from "node:assert/strict";
import test from "node:test";
import { validateMapSearch } from "../lib/map-search";

test("map links restore ordered elevation bounds and accept older minimum-only links", () => {
	function bounds(input: Record<string, unknown>) {
		const { minElevation, maxElevation } = validateMapSearch(input);
		return [minElevation, maxElevation];
	}
	assert.deepEqual(bounds({}), [5000, 10000]);
	assert.deepEqual(bounds({ minElevation: 5500 }), [5500, 10000]);
	assert.deepEqual(bounds({ minElevation: 15000 }), [10000, 10000]);
	assert.deepEqual(
		bounds({ minElevation: 8000, maxElevation: 3000 }),
		[3000, 8000],
	);
	assert.deepEqual(
		bounds({ minElevation: 0, maxElevation: 4300.6 }),
		[0, 4301],
	);
	assert.deepEqual(
		bounds({ minElevation: -1, maxElevation: 15000 }),
		[5000, 10000],
	);
});
