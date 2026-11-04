/** Incoming-arc field with several independently paid initial positions. */
import { MinQueue } from "./coarse_osm_min_queue_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import {
	type SearchOptions,
	TWELVE_HOURS_TICKS,
} from "./coarse_osm_packed_search_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import {
	type RoadPosition,
	resolveRoadPosition,
} from "./coarse_osm_paid_positions_v1.ts";
import {
	type PaidProgress,
	UNREACHED_SECONDS,
} from "./coarse_osm_road_field_v1.ts";

const UNREACHED = 0xffffffff,
	ENTRY_ONLY = 0x80000000;
export type AccessStart = { position: RoadPosition; initialTicks: number };
function integer(value: number, maximum: number, label: string) {
	if (!Number.isInteger(value) || value < 0 || value > maximum)
		throw new Error(`Access field ${label} domain`);
}
const portion = (full: number, units: number, empty: boolean) =>
	empty ? 0 : Math.max(1, Math.min(full, Math.ceil((full * units) / 65535)));

/** Exactly64 backing bytes per initial state, including two entry-shadow slots. */
export class AccessSeeds {
	readonly buffer: ArrayBuffer;
	readonly rank: Float64Array;
	readonly forward: Float64Array;
	readonly backward: Float64Array;
	readonly arcs: Uint32Array;
	readonly initial: Uint32Array;
	readonly vertex: Int32Array;
	readonly next: Int32Array;
	readonly shadowKeys: Uint32Array;
	readonly shadowEntry: Uint32Array;
	readonly forwardRemaining: Uint32Array;
	readonly backwardRemaining: Uint32Array;
	readonly firstByArc = new Map<number, number>();
	readonly vertexInitial = new Map<number, number>();
	readonly shadowIndex = new Map<number, number>();
	constructor(
		graph: PackedCarGraph,
		geometry: PaidRoadGeometry,
		starts: AccessStart[],
	) {
		if (starts.length < 1 || starts.length > 4096)
			throw new Error("Access field source count domain");
		const n = starts.length;
		this.buffer = new ArrayBuffer(64 * n);
		this.rank = new Float64Array(this.buffer, 0, n);
		this.forward = new Float64Array(this.buffer, 8 * n, n);
		this.backward = new Float64Array(this.buffer, 16 * n, n);
		this.arcs = new Uint32Array(this.buffer, 24 * n, n);
		this.initial = new Uint32Array(this.buffer, 28 * n, n);
		this.vertex = new Int32Array(this.buffer, 32 * n, n).fill(-1);
		this.next = new Int32Array(this.buffer, 36 * n, n).fill(-1);
		this.shadowKeys = new Uint32Array(this.buffer, 40 * n, 2 * n);
		this.shadowEntry = new Uint32Array(this.buffer, 48 * n, 2 * n).fill(
			UNREACHED,
		);
		this.forwardRemaining = new Uint32Array(this.buffer, 56 * n, n);
		this.backwardRemaining = new Uint32Array(this.buffer, 60 * n, n);
		starts.forEach((start, i) => {
			integer(start.initialTicks, TWELVE_HOURS_TICKS, "initial cost");
			const p = resolveRoadPosition(graph, geometry, start.position),
				arc = p.canonicalArc;
			this.rank[i] = p.rank;
			this.forward[i] = p.forwardUnits;
			this.backward[i] = p.backwardUnits;
			this.arcs[i] = arc;
			this.initial[i] = start.initialTicks;
			this.next[i] = this.firstByArc.get(arc) ?? -1;
			this.firstByArc.set(arc, i);
			if ("vertex" in p.source) {
				this.vertex[i] = p.source.vertex;
				this.vertexInitial.set(
					p.source.vertex,
					Math.min(
						this.vertexInitial.get(p.source.vertex) ?? UNREACHED,
						start.initialTicks,
					),
				);
			} else
				for (const part of p.source.partials) {
					if (part.arc === arc) this.forwardRemaining[i] = part.ticks;
					else this.backwardRemaining[i] = part.ticks;
					if (!this.shadowIndex.has(part.arc)) {
						const slot = this.shadowIndex.size;
						this.shadowIndex.set(part.arc, slot);
						this.shadowKeys[slot] = part.arc;
					}
				}
		});
	}
	forArc(arc: number, visit: (i: number) => void) {
		for (let i = this.firstByArc.get(arc) ?? -1; i !== -1; i = this.next[i])
			visit(i);
	}
	earliest(arc: number) {
		let ticks = Infinity;
		for (let i = this.firstByArc.get(arc) ?? -1; i !== -1; i = this.next[i]) {
			ticks = Math.min(ticks, this.initial[i]);
		}
		return ticks;
	}
	get count() {
		return this.arcs.length;
	}
}
export type AccessRoadField = {
	horizonTicks: number;
	labels: Uint32Array;
	vertexArrivalSeconds: Uint16Array;
	seeds: AccessSeeds;
	source: {
		canonicalArc: number;
		rank: number;
		forwardUnits: number;
		backwardUnits: number;
		initialTicks: number;
		vertex: number | null;
	};
	stats: {
		settles: number;
		maximumHeapEntries: number;
		maximumBackingBufferBytes: number;
		returnedBackingBufferBytes: number;
		seedBackingBufferBytes: number;
		starts: number;
	};
};

function compute(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	starts: AccessStart[],
	maximum: number,
	options: SearchOptions,
): AccessRoadField {
	const horizonTicks = options.maxTicks ?? maximum,
		heapEntries = options.maxHeapEntries ?? 1000000,
		maxSettles = options.maxSettles ?? 40000000;
	integer(horizonTicks, maximum, "horizon");
	integer(heapEntries, 1000000, "heap");
	integer(maxSettles, 40000000, "settles");
	if (starts.length < 1 || starts.length > 4096)
		throw new Error("Access field source count domain");
	const backing =
		4 * graph.arcs + 2 * graph.vertices + 8 * heapEntries + 64 * starts.length;
	if (backing > 67108864)
		throw new Error("Access field scratch backing limit exceeded");
	options.check?.();
	const seeds = new AccessSeeds(graph, geometry, starts),
		labels = new Uint32Array(graph.arcs).fill(UNREACHED),
		vertices = new Uint16Array(graph.vertices).fill(UNREACHED_SECONDS),
		heap = new MinQueue(heapEntries);
	const offerHead = (arc: number, cost: number) => {
		if (cost > horizonTicks || cost >= labels[arc]) return;
		labels[arc] = cost;
		const target = graph.arcTarget(arc);
		vertices[target] = Math.min(vertices[target], Math.ceil(cost / 8));
		heap.push(arc, cost);
	};
	const offerEntry = (arc: number, entry: number) => {
		if (entry > horizonTicks) return;
		const slot = seeds.shadowIndex.get(arc);
		if (slot !== undefined)
			seeds.shadowEntry[slot] = Math.min(seeds.shadowEntry[slot], entry);
		const head = entry + graph.arcCostTicks(arc);
		if (head <= horizonTicks) offerHead(arc, head);
		else if (
			labels[arc] === UNREACHED ||
			(labels[arc] >= ENTRY_ONLY && entry < labels[arc] - ENTRY_ONLY)
		)
			labels[arc] = ENTRY_ONLY + entry;
	};
	for (let i = 0; i < seeds.count; i++) {
		const initial = seeds.initial[i];
		if (initial > horizonTicks) continue;
		const vertex = seeds.vertex[i],
			arc = seeds.arcs[i];
		if (vertex >= 0) {
			vertices[vertex] = Math.min(vertices[vertex], Math.ceil(initial / 8));
			for (
				let following = graph.outgoingStart(vertex);
				following < graph.outgoingEnd(vertex);
				following++
			)
				offerEntry(following, initial);
		} else {
			offerHead(arc, initial + seeds.forwardRemaining[i]);
			const reverse = graph.reverseArc(arc);
			if (reverse !== null)
				offerHead(reverse, initial + seeds.backwardRemaining[i]);
		}
	}
	let settles = 0;
	while (heap.length) {
		const [arc, cost] = heap.pop();
		if (labels[arc] !== cost) continue;
		if (++settles > maxSettles)
			throw new Error("Access field settle limit exceeded");
		if ((settles & 1023) === 0) options.check?.();
		const vertex = graph.arcTarget(arc),
			flags = graph.nodeFlags(vertex);
		if (flags & 1) continue;
		const reverse = graph.reverseArc(arc);
		for (
			let following = graph.outgoingStart(vertex);
			following < graph.outgoingEnd(vertex);
			following++
		) {
			const reversal = following === reverse;
			if ((reversal && !(flags & 4)) || graph.forbidsTurn(arc, following))
				continue;
			offerEntry(following, cost + (flags & 2 ? 40 : 0) + (reversal ? 160 : 0));
		}
	}
	options.check?.();
	return {
		horizonTicks,
		labels,
		vertexArrivalSeconds: vertices,
		seeds,
		source: {
			canonicalArc: seeds.arcs[0],
			rank: seeds.rank[0],
			forwardUnits: seeds.forward[0],
			backwardUnits: seeds.backward[0],
			initialTicks: seeds.initial[0],
			vertex: seeds.vertex[0] < 0 ? null : seeds.vertex[0],
		},
		stats: {
			settles,
			maximumHeapEntries: heap.peak,
			maximumBackingBufferBytes: backing,
			returnedBackingBufferBytes:
				labels.byteLength + vertices.byteLength + seeds.buffer.byteLength,
			seedBackingBufferBytes: seeds.buffer.byteLength,
			starts: seeds.count,
		},
	};
}
export function computeAccessRoadField(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	starts: AccessStart[],
	options: SearchOptions = {},
) {
	return compute(graph, geometry, starts, TWELVE_HOURS_TICKS, options);
}
export function computeDiagnosticAccessRoadField(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	starts: AccessStart[],
	options: SearchOptions = {},
) {
	return compute(graph, geometry, starts, 432000, options);
}
export function accessArcEntryTicks(
	graph: PackedCarGraph,
	field: AccessRoadField,
	arc: number,
): number | null {
	graph.arcCostTicks(arc);
	const slot = field.seeds.shadowIndex.get(arc);
	if (slot !== undefined)
		return field.seeds.shadowEntry[slot] === UNREACHED
			? null
			: field.seeds.shadowEntry[slot];
	const label = field.labels[arc];
	return label === UNREACHED
		? null
		: label >= ENTRY_ONLY
			? label - ENTRY_ONLY
			: label - graph.arcCostTicks(arc);
}
export function arrivalAtAccessProgress(
	graph: PackedCarGraph,
	field: AccessRoadField,
	p: PaidProgress,
): number | null {
	const { canonicalArc: arc, rank, lastRank, forwardUnits, backwardUnits } = p;
	if (
		![rank, lastRank, forwardUnits, backwardUnits].every(Number.isFinite) ||
		rank < 0 ||
		rank > lastRank ||
		lastRank < 1 ||
		forwardUnits < 0 ||
		forwardUnits > 65535 ||
		backwardUnits < 0 ||
		backwardUnits > 65535
	)
		throw new Error("Access field progress domain");
	const reverse = graph.reverseArc(arc);
	if (reverse !== null && reverse < arc)
		throw new Error("Access field canonical position required");
	let best: number | null = null;
	const offer = (ticks: number) => {
		if (ticks <= field.horizonTicks && (best === null || ticks < best))
			best = ticks;
	};
	const vertex =
		rank === 0
			? graph.arcTail(arc)
			: rank === lastRank
				? graph.arcTarget(arc)
				: null;
	if (
		vertex !== null &&
		field.vertexArrivalSeconds[vertex] !== UNREACHED_SECONDS
	) {
		best = field.vertexArrivalSeconds[vertex] * 8;
		const initial = field.seeds.vertexInitial.get(vertex);
		if (initial !== undefined) offer(initial);
	}
	const entry = accessArcEntryTicks(graph, field, arc);
	if (entry !== null)
		offer(entry + portion(graph.arcCostTicks(arc), forwardUnits, rank === 0));
	if (reverse !== null) {
		const back = accessArcEntryTicks(graph, field, reverse);
		if (back !== null)
			offer(
				back +
					portion(
						graph.arcCostTicks(reverse),
						65535 - backwardUnits,
						rank === lastRank,
					),
			);
	}
	for (
		let i = field.seeds.firstByArc.get(arc) ?? -1;
		i !== -1;
		i = field.seeds.next[i]
	) {
		if (rank >= field.seeds.rank[i])
			offer(
				field.seeds.initial[i] +
					portion(
						graph.arcCostTicks(arc),
						forwardUnits - field.seeds.forward[i],
						rank === field.seeds.rank[i],
					),
			);
		if (reverse !== null && rank <= field.seeds.rank[i])
			offer(
				field.seeds.initial[i] +
					portion(
						graph.arcCostTicks(reverse),
						field.seeds.backward[i] - backwardUnits,
						rank === field.seeds.rank[i],
					),
			);
	}
	return best;
}
export function arrivalAtAccessPosition(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	field: AccessRoadField,
	position: RoadPosition,
) {
	const p = resolveRoadPosition(graph, geometry, position);
	let count = 0;
	geometry.visitPoints(position.canonicalArc, () => {
		count++;
	});
	return arrivalAtAccessProgress(graph, field, {
		canonicalArc: p.canonicalArc,
		rank: p.rank,
		lastRank: count - 1,
		forwardUnits: p.forwardUnits,
		backwardUnits: p.backwardUnits,
	});
}
export function restoreAccessVertices(
	graph: PackedCarGraph,
	field: AccessRoadField,
) {
	field.vertexArrivalSeconds.fill(UNREACHED_SECONDS);
	for (let arc = 0; arc < graph.arcs; arc++)
		if (field.labels[arc] < ENTRY_ONLY) {
			const v = graph.arcTarget(arc);
			field.vertexArrivalSeconds[v] = Math.min(
				field.vertexArrivalSeconds[v],
				Math.ceil(field.labels[arc] / 8),
			);
		}
	for (const [vertex, ticks] of field.seeds.vertexInitial)
		if (ticks <= field.horizonTicks)
			field.vertexArrivalSeconds[vertex] = Math.min(
				field.vertexArrivalSeconds[vertex],
				Math.ceil(ticks / 8),
			);
}
