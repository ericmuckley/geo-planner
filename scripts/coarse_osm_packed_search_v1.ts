/** Bounded incoming-arc Dijkstra for the offline packed candidate. */
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";

export type PackedPoint =
	| { vertex: number }
	| { partials: readonly { arc: number; ticks: number }[] };

export type SearchOptions = {
	maxTicks?: number;
	maxHeapEntries?: number;
	maxSettles?: number;
	check?: () => void;
};

const UNREACHED = 0xffffffff;
export const TWELVE_HOURS_TICKS = 12 * 60 * 60 * 8;

function integer(value: number, maximum: number, name: string): void {
	if (!Number.isInteger(value) || value < 0 || value > maximum) {
		throw new RangeError(`Invalid packed search ${name}`);
	}
}

class Heap {
	readonly arcs: Uint32Array;
	readonly costs: Uint32Array;
	length = 0;

	constructor(capacity: number) {
		this.arcs = new Uint32Array(capacity);
		this.costs = new Uint32Array(capacity);
	}

	push(arc: number, cost: number): void {
		if (this.length === this.arcs.length) {
			throw new Error("Packed search heap limit exceeded");
		}
		let position = this.length++;
		while (position > 0) {
			const parent = (position - 1) >>> 1;
			if (this.costs[parent] <= cost) break;
			this.arcs[position] = this.arcs[parent];
			this.costs[position] = this.costs[parent];
			position = parent;
		}
		this.arcs[position] = arc;
		this.costs[position] = cost;
	}

	pop(): [number, number] {
		const arc = this.arcs[0];
		const cost = this.costs[0];
		const last = --this.length;
		const replacement = this.arcs[last];
		const replacementCost = this.costs[last];
		let position = 0;
		while (2 * position + 1 < last) {
			let child = 2 * position + 1;
			if (child + 1 < last && this.costs[child + 1] < this.costs[child]) {
				child++;
			}
			if (this.costs[child] >= replacementCost) break;
			this.arcs[position] = this.arcs[child];
			this.costs[position] = this.costs[child];
			position = child;
		}
		this.arcs[position] = replacement;
		this.costs[position] = replacementCost;
		return [arc, cost];
	}
}

function validatePoint(graph: PackedCarGraph, point: PackedPoint): void {
	if ("vertex" in point) {
		graph.nodeFlags(point.vertex);
	} else {
		if (!Array.isArray(point.partials) || point.partials.length > 1024) {
			throw new Error("Packed point partial limit");
		}
		const seen = new Set<number>();
		for (const { arc, ticks } of point.partials) {
			integer(ticks, graph.arcCostTicks(arc), "partial cost");
			if (seen.has(arc)) throw new Error("Duplicate packed partial arc");
			seen.add(arc);
		}
	}
}

/**
 * Partial points must be paid, direction-legal offsets on their declared arcs.
 * The geometry adapter must supply a same-span direct cost separately when both
 * endpoints lie inside that span. Null means no route within the given horizon.
 */
export function searchPackedCar(
	graph: PackedCarGraph,
	source: PackedPoint,
	target: PackedPoint,
	options: SearchOptions = {},
): { ticks: number | null; settles: number; searchBufferBytes: number } {
	const maxTicks = options.maxTicks ?? TWELVE_HOURS_TICKS;
	const maxHeap = options.maxHeapEntries ?? 1_000_000;
	const maxSettles = options.maxSettles ?? 40_000_000;
	integer(maxTicks, TWELVE_HOURS_TICKS, "horizon");
	integer(maxHeap, 1_000_000, "heap capacity");
	integer(maxSettles, 40_000_000, "settle limit");
	validatePoint(graph, source);
	validatePoint(graph, target);
	options.check?.();
	if (
		"vertex" in source &&
		"vertex" in target &&
		source.vertex === target.vertex
	) {
		return { ticks: 0, settles: 0, searchBufferBytes: 0 };
	}
	const labels = new Uint32Array(graph.arcs).fill(UNREACHED);
	const heap = new Heap(maxHeap);
	const stops = new Map(
		"partials" in target
			? target.partials.map(({ arc, ticks }) => [arc, ticks])
			: [],
	);
	let best = UNREACHED;
	let settles = 0;
	function finish(cost: number): void {
		if (cost <= maxTicks && cost < best) best = cost;
	}
	function offer(arc: number, cost: number): void {
		if (cost <= maxTicks && cost <= best && cost < labels[arc]) {
			labels[arc] = cost;
			heap.push(arc, cost);
		}
	}
	if ("vertex" in source) {
		for (
			let arc = graph.outgoingStart(source.vertex);
			arc < graph.outgoingEnd(source.vertex);
			arc++
		) {
			const stop = stops.get(arc);
			if (stop !== undefined) finish(stop);
			offer(arc, graph.arcCostTicks(arc));
		}
	} else {
		for (const { arc, ticks } of source.partials) offer(arc, ticks);
	}
	while (heap.length) {
		const [arc, cost] = heap.pop();
		if (labels[arc] !== cost) continue;
		if (cost > best) break;
		if (++settles > maxSettles) {
			throw new Error("Packed search settle limit exceeded");
		}
		if ((settles & 1023) === 0) options.check?.();
		const vertex = graph.arcTarget(arc);
		if ("vertex" in target && vertex === target.vertex) finish(cost);
		const flags = graph.nodeFlags(vertex);
		if (flags & 1) continue;
		const reverse = graph.reverseArc(arc);
		const end = graph.outgoingEnd(vertex);
		for (
			let following = graph.outgoingStart(vertex);
			following < end;
			following++
		) {
			const reversal = following === reverse;
			if ((reversal && !(flags & 4)) || graph.forbidsTurn(arc, following))
				continue;
			const delay = (flags & 2 ? 40 : 0) + (reversal ? 160 : 0);
			const stop = stops.get(following);
			if (stop !== undefined) finish(cost + delay + stop);
			offer(following, cost + delay + graph.arcCostTicks(following));
		}
	}
	return {
		ticks: best === UNREACHED ? null : best,
		settles,
		searchBufferBytes:
			labels.byteLength + heap.arcs.byteLength + heap.costs.byteLength,
	};
}
