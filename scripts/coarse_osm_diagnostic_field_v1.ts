/** Offline 900-minute diagnostic only; V1 production/query semantics stay capped at 720. */
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

const UNREACHED = 0xffffffff;
const ENTRY_ONLY = 0x80000000;
export const UNREACHED_SECONDS = 65535;
type PartialSeed = {
	arc: number;
	remainingTicks: number;
	regularEntryTicks: number;
};
export type RoadField = {
	horizonTicks: number;
	labels: Uint32Array;
	vertexArrivalSeconds: Uint16Array;
	partials: PartialSeed[];
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
	};
};

function integer(value: number, maximum: number, label: string) {
	if (!Number.isInteger(value) || value < 0 || value > maximum)
		throw new Error(`Road field ${label} domain`);
}
function portionTicks(full: number, units: number, empty: boolean) {
	return empty
		? 0
		: Math.max(1, Math.min(full, Math.ceil((full * units) / 65535)));
}

export function computeDiagnosticRoadField(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	position: RoadPosition,
	initialTicks: number,
	options: SearchOptions = {},
): RoadField {
	const horizonTicks = options.maxTicks ?? 432000;
	const heapEntries = options.maxHeapEntries ?? 1000000;
	const maxSettles = options.maxSettles ?? 40000000;
	integer(horizonTicks, 432000, "horizon");
	integer(initialTicks, TWELVE_HOURS_TICKS, "initial cost");
	integer(heapEntries, 1000000, "heap");
	integer(maxSettles, 40000000, "settles");
	if (4 * graph.arcs + 2 * graph.vertices + 8 * heapEntries > 67108864)
		throw new Error("Road field scratch backing limit exceeded");
	const located = resolveRoadPosition(graph, geometry, position);
	options.check?.();
	const labels = new Uint32Array(graph.arcs).fill(UNREACHED);
	const vertices = new Uint16Array(graph.vertices).fill(UNREACHED_SECONDS);
	const heap = new MinQueue(heapEntries);
	const partials: PartialSeed[] =
		"partials" in located.source
			? located.source.partials.map((part) => ({
					arc: part.arc,
					remainingTicks: part.ticks,
					regularEntryTicks: UNREACHED,
				}))
			: [];
	const sourceVertex =
		"vertex" in located.source ? located.source.vertex : null;
	let settles = 0;
	const seedFor = (arc: number) =>
		partials[0]?.arc === arc
			? partials[0]
			: partials[1]?.arc === arc
				? partials[1]
				: undefined;
	const offerHead = (arc: number, cost: number) => {
		if (cost > horizonTicks || cost >= labels[arc]) return;
		labels[arc] = cost;
		vertices[graph.arcTarget(arc)] = Math.min(
			vertices[graph.arcTarget(arc)],
			Math.ceil(cost / 8),
		);
		heap.push(arc, cost);
	};
	const offerEntry = (arc: number, entry: number) => {
		if (entry > horizonTicks) return;
		const seed = seedFor(arc);
		if (seed) seed.regularEntryTicks = Math.min(seed.regularEntryTicks, entry);
		const head = entry + graph.arcCostTicks(arc);
		if (head <= horizonTicks) offerHead(arc, head);
		else if (
			labels[arc] === UNREACHED ||
			(labels[arc] >= ENTRY_ONLY && entry < labels[arc] - ENTRY_ONLY)
		)
			labels[arc] = ENTRY_ONLY + entry;
	};
	if (initialTicks <= horizonTicks) {
		if (sourceVertex !== null) {
			vertices[sourceVertex] = Math.ceil(initialTicks / 8);
			for (
				let arc = graph.outgoingStart(sourceVertex);
				arc < graph.outgoingEnd(sourceVertex);
				arc++
			)
				offerEntry(arc, initialTicks);
		} else
			for (const seed of partials)
				offerHead(seed.arc, initialTicks + seed.remainingTicks);
	}
	while (heap.length) {
		const [arc, cost] = heap.pop();
		if (labels[arc] !== cost) continue;
		if (++settles > maxSettles)
			throw new Error("Road field settle limit exceeded");
		if ((settles & 1023) === 0) options.check?.();
		const vertex = graph.arcTarget(arc);
		const flags = graph.nodeFlags(vertex);
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
	const returnedBackingBufferBytes = labels.byteLength + vertices.byteLength;
	const maximumBackingBufferBytes =
		returnedBackingBufferBytes + heap.keys.byteLength + heap.costs.byteLength;
	if (maximumBackingBufferBytes > 67108864)
		throw new Error("Road field scratch backing limit exceeded");
	return {
		horizonTicks,
		labels,
		vertexArrivalSeconds: vertices,
		partials,
		source: {
			canonicalArc: located.canonicalArc,
			rank: located.rank,
			forwardUnits: located.forwardUnits,
			backwardUnits: located.backwardUnits,
			initialTicks,
			vertex: sourceVertex,
		},
		stats: {
			settles,
			maximumHeapEntries: heap.peak,
			maximumBackingBufferBytes,
			returnedBackingBufferBytes,
		},
	};
}

export function regularArcEntryTicks(
	graph: PackedCarGraph,
	field: RoadField,
	arc: number,
): number | null {
	graph.arcCostTicks(arc);
	const seed =
		field.partials[0]?.arc === arc
			? field.partials[0]
			: field.partials[1]?.arc === arc
				? field.partials[1]
				: undefined;
	if (seed)
		return seed.regularEntryTicks === UNREACHED ? null : seed.regularEntryTicks;
	const value = field.labels[arc];
	if (value === UNREACHED) return null;
	return value >= ENTRY_ONLY
		? value - ENTRY_ONLY
		: value - graph.arcCostTicks(arc);
}

export type PaidProgress = {
	canonicalArc: number;
	rank: number;
	lastRank: number;
	forwardUnits: number;
	backwardUnits: number;
};

/** Non-null means reachable; a vertex value can be upward rounded by <=7 ticks. */
export function arrivalAtPaidProgress(
	graph: PackedCarGraph,
	field: RoadField,
	point: PaidProgress,
): number | null {
	const {
		canonicalArc: arc,
		rank,
		lastRank,
		forwardUnits,
		backwardUnits,
	} = point;
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
		throw new Error("Road field progress domain");
	const reverse = graph.reverseArc(arc);
	if (reverse !== null && reverse < arc)
		throw new Error("Road field canonical position required");
	let best: number | null = null;
	const offer = (value: number) => {
		if (value <= field.horizonTicks && (best === null || value < best))
			best = value;
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
		if (field.source.vertex === vertex) offer(field.source.initialTicks);
	}
	const forwardEntry = regularArcEntryTicks(graph, field, arc);
	if (forwardEntry !== null)
		offer(
			forwardEntry +
				portionTicks(graph.arcCostTicks(arc), forwardUnits, rank === 0),
		);
	if (reverse !== null) {
		const backEntry = regularArcEntryTicks(graph, field, reverse);
		if (backEntry !== null)
			offer(
				backEntry +
					portionTicks(
						graph.arcCostTicks(reverse),
						65535 - backwardUnits,
						rank === lastRank,
					),
			);
	}
	const source = field.source;
	if (arc === source.canonicalArc) {
		if (rank >= source.rank)
			offer(
				source.initialTicks +
					portionTicks(
						graph.arcCostTicks(arc),
						forwardUnits - source.forwardUnits,
						rank === source.rank,
					),
			);
		if (reverse !== null && rank <= source.rank)
			offer(
				source.initialTicks +
					portionTicks(
						graph.arcCostTicks(reverse),
						source.backwardUnits - backwardUnits,
						rank === source.rank,
					),
			);
	}
	return best;
}

export function arrivalAtRoadPosition(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	field: RoadField,
	position: RoadPosition,
): number | null {
	const point = resolveRoadPosition(graph, geometry, position);
	let points = 0;
	geometry.visitPoints(position.canonicalArc, () => {
		points++;
	});
	return arrivalAtPaidProgress(graph, field, {
		canonicalArc: point.canonicalArc,
		rank: point.rank,
		lastRank: points - 1,
		forwardUnits: point.forwardUnits,
		backwardUnits: point.backwardUnits,
	});
}
