/** Same incoming-arc search, with the unused vertex summary borrowed by its heap. */
import {
	type AccessRoadField,
	AccessSeeds,
	type AccessStart,
	restoreAccessVertices,
} from "./coarse_osm_access_road_field_v1.ts";
import { BorrowedQueue } from "./coarse_osm_borrowed_queue_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import {
	type SearchOptions,
	TWELVE_HOURS_TICKS,
} from "./coarse_osm_packed_search_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import { UNREACHED_SECONDS } from "./coarse_osm_road_field_v1.ts";

export {
	type AccessRoadField,
	AccessSeeds,
	type AccessStart,
	accessArcEntryTicks,
	arrivalAtAccessPosition,
	arrivalAtAccessProgress,
	restoreAccessVertices,
} from "./coarse_osm_access_road_field_v1.ts";

const UNREACHED = 0xffffffff,
	ENTRY_ONLY = 0x80000000;
function integer(value: number, maximum: number, label: string) {
	if (!Number.isInteger(value) || value < 0 || value > maximum)
		throw new Error(`Access field ${label} domain`);
}

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
	const borrowed = 2 * graph.vertices >= 8 * heapEntries;
	const backing =
		4 * graph.arcs +
		2 * graph.vertices +
		(borrowed ? 0 : 8 * heapEntries) +
		64 * starts.length;
	if (backing > 67108864)
		throw new Error("Access field scratch backing limit exceeded");
	options.check?.();
	const seeds = new AccessSeeds(graph, geometry, starts),
		labels = new Uint32Array(graph.arcs).fill(UNREACHED),
		vertices = new Uint16Array(graph.vertices).fill(UNREACHED_SECONDS),
		queueBuffer = borrowed ? vertices.buffer : new ArrayBuffer(8 * heapEntries),
		heap = new BorrowedQueue(
			new Uint32Array(queueBuffer, 0, heapEntries),
			new Uint32Array(queueBuffer, 4 * heapEntries, heapEntries),
		);
	const offerHead = (arc: number, cost: number) => {
		if (cost > horizonTicks || cost >= labels[arc]) return;
		labels[arc] = cost;
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
	const field: AccessRoadField = {
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
	// Vertex minima are not search state. Restore them after the queue releases
	// its borrowed view, using the same sealed restoration as display rendering.
	restoreAccessVertices(graph, field);
	options.check?.();
	return field;
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
