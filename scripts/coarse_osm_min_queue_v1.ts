/** Fixed-capacity queue shared by bounded offline candidate algorithms. */
export class MinQueue {
	readonly keys: Uint32Array;
	readonly costs: Uint32Array;
	length = 0;
	peak = 0;
	constructor(capacity: number) {
		if (!Number.isInteger(capacity) || capacity < 0 || capacity > 1000000)
			throw new Error("Queue capacity domain");
		this.keys = new Uint32Array(capacity);
		this.costs = new Uint32Array(capacity);
	}
	push(key: number, cost: number) {
		if (this.length === this.keys.length)
			throw new Error("Road field heap limit exceeded");
		let position = this.length++;
		this.peak = Math.max(this.peak, this.length);
		while (position > 0) {
			const parent = (position - 1) >>> 1;
			if (this.costs[parent] <= cost) break;
			this.keys[position] = this.keys[parent];
			this.costs[position] = this.costs[parent];
			position = parent;
		}
		this.keys[position] = key;
		this.costs[position] = cost;
	}
	pop(): [number, number] {
		if (!this.length) throw new Error("Empty road field queue");
		const key = this.keys[0];
		const cost = this.costs[0];
		const last = --this.length;
		const replacement = this.keys[last];
		const replacementCost = this.costs[last];
		let position = 0;
		while (2 * position + 1 < last) {
			let child = 2 * position + 1;
			if (child + 1 < last && this.costs[child + 1] < this.costs[child])
				child++;
			if (this.costs[child] >= replacementCost) break;
			this.keys[position] = this.keys[child];
			this.costs[position] = this.costs[child];
			position = child;
		}
		this.keys[position] = replacement;
		this.costs[position] = replacementCost;
		return [key, cost];
	}
}
