/** The sealed heap algorithm with validated caller-owned, disjoint views. */
import { DisplayQueue } from "./coarse_osm_display_grid_v1.ts";

export class BorrowedQueue extends DisplayQueue {
	constructor(keys: Uint32Array, costs: Uint32Array) {
		super(keys, costs);
		if (keys.length !== costs.length || keys.length > 1000000)
			throw new Error("Queue capacity domain");
		if (
			keys.buffer === costs.buffer &&
			keys.byteOffset < costs.byteOffset + costs.byteLength &&
			costs.byteOffset < keys.byteOffset + keys.byteLength
		)
			throw new Error("Queue views overlap");
	}
	push(key: number, cost: number) {
		if (this.length === this.keys.length)
			throw new Error("Road field heap limit exceeded");
		super.push(key, cost);
	}
}
