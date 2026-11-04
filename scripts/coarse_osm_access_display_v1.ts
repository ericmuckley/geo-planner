/** Paid initial-access field display; no local-to-road feedback. */
import { landConnection } from "../src/server/coarse-geography.ts";
import {
	type AccessRoadField,
	accessArcEntryTicks,
	arrivalAtAccessProgress,
	restoreAccessVertices,
} from "./coarse_osm_access_road_field_v1.ts";
import {
	boundedContours,
	type ContourLimits,
} from "./coarse_osm_display_contours_v1.ts";
import {
	bit,
	cellAt,
	center,
	DisplayLimit,
	DisplayQueue,
	fillLocal,
	localCosts,
	makeFrame,
	rasterLand,
	rasterLinks,
	setBit,
	setNibble,
} from "./coarse_osm_display_grid_v1.ts";
import {
	type DisplayOptions,
	roadCoordinate,
} from "./coarse_osm_filled_display_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import { UNREACHED_SECONDS } from "./coarse_osm_road_field_v1.ts";
import {
	type Coordinate,
	EARTH_METERS,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";

const CAP = 67108864,
	MAX_CELLS = 2500000,
	CURVE_POINTS = 4096;
const RAD = Math.PI / 180;
const LIMITS: ContourLimits = { edges: 400000, rings: 4096, vertices: 100000 };
function checkedOptions(options: DisplayOptions) {
	const cells = options.maxCells ?? MAX_CELLS,
		heap = options.heapEntries ?? 1000000;
	const json = options.maxJsonBytes ?? 3000000,
		limits = options.contourLimits ?? LIMITS;
	for (const [value, maximum] of [
		[cells, MAX_CELLS],
		[heap, 1000000],
		[json, 3000000],
		[limits.edges, LIMITS.edges],
		[limits.rings, LIMITS.rings],
		[limits.vertices, LIMITS.vertices],
	])
		if (!Number.isInteger(value) || value < 1 || value > maximum)
			throw new Error("Display limit domain");
	return { cells, heap, json, limits };
}

function renderAccess(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	connection: OriginConnection,
	field: AccessRoadField,
	options: DisplayOptions,
	maximumHorizon: number,
) {
	const began = performance.now(),
		check = options.check ?? (() => {}),
		limits = checkedOptions(options);
	if (
		field.labels.length !== graph.arcs ||
		field.vertexArrivalSeconds.length !== graph.vertices ||
		field.horizonTicks > maximumHorizon ||
		field.source.initialTicks !== connection.connectorTicks ||
		field.source.canonicalArc !== connection.snap.canonicalArc
	)
		throw new Error("Display field/source mismatch");
	// These fixed upper dimensions include an outward edge alignment at the finest step.
	const maxWidth =
		Math.ceil((geography.bounds[2] - geography.bounds[0]) * 200) + 2;
	const maxHeight =
		Math.ceil((geography.bounds[3] - geography.bounds[1]) * 200) + 2;
	const rasterBytes = 2 * limits.cells + maxWidth + maxHeight + 1;
	const bitBytes = Math.ceil(limits.cells / 8),
		nibbleBytes = Math.ceil(limits.cells / 2);
	const borrowed =
		field.vertexArrivalSeconds.byteOffset % 4 === 0 &&
		field.vertexArrivalSeconds.byteLength >= 8 * limits.heap;
	const extraQueue = borrowed ? 0 : 8 * limits.heap;
	const addedBytes =
		rasterBytes +
		3 * bitBytes +
		2 * nibbleBytes +
		2 * maxWidth +
		4 * maxHeight +
		12 * CURVE_POINTS +
		extraQueue;
	const scratch = field.stats.maximumBackingBufferBytes + addedBytes;
	if (scratch > CAP) throw new Error("Display scratch backing limit exceeded");
	check();
	const raster = new ArrayBuffer(rasterBytes),
		times = new Uint16Array(raster, 0, limits.cells);
	const land = new Uint8Array(bitBytes),
		boundary = new Uint8Array(bitBytes),
		coverage = new Uint8Array(bitBytes);
	const parents = new Uint8Array(nibbleBytes),
		links = new Uint8Array(nibbleBytes),
		row = new Uint8Array(2 * maxWidth);
	const horizontal = new Uint16Array(maxHeight),
		diagonal = new Uint16Array(maxHeight);
	const xy = new Int32Array(2 * CURVE_POINTS),
		prefixes = new Uint16Array(2 * CURVE_POINTS);
	const queueBuffer = borrowed
		? field.vertexArrivalSeconds.buffer
		: new ArrayBuffer(extraQueue);
	const queueOffset = borrowed ? field.vertexArrivalSeconds.byteOffset : 0;
	const heap = new DisplayQueue(
		new Uint32Array(queueBuffer, queueOffset, limits.heap),
		new Uint32Array(queueBuffer, queueOffset + 4 * limits.heap, limits.heap),
	);
	const horizon = Math.floor(field.horizonTicks / 8);
	let curveCount = 0;
	const pointAt = (i: number): Coordinate => [
		xy[2 * i] / 1e7,
		xy[2 * i + 1] / 1e7,
	];
	const activeSpans = (visit: (arc: number, earliest: number) => void) => {
		for (let tail = 0; tail < graph.vertices; tail++) {
			if ((tail & 65535) === 0) check();
			for (
				let arc = graph.outgoingStart(tail);
				arc < graph.outgoingEnd(tail);
				arc++
			) {
				const reverse = graph.reverseArc(arc);
				if (reverse !== null && reverse < arc) continue;
				const head = graph.arcTarget(arc);
				let earliest = Infinity;
				for (const vertex of [tail, head])
					if (field.vertexArrivalSeconds[vertex] !== UNREACHED_SECONDS)
						earliest = Math.min(
							earliest,
							Math.max(0, field.vertexArrivalSeconds[vertex] * 8 - 7),
						);
				if (field.labels[arc] !== 0xffffffff)
					earliest = Math.min(
						earliest,
						accessArcEntryTicks(graph, field, arc) ?? Infinity,
					);
				if (reverse !== null && field.labels[reverse] !== 0xffffffff)
					earliest = Math.min(
						earliest,
						accessArcEntryTicks(graph, field, reverse) ?? Infinity,
					);
				earliest = Math.min(earliest, field.seeds.earliest(arc));
				if (earliest > field.horizonTicks) continue;
				curveCount = 0;
				geometry.visitPoints(arc, (point) => {
					if (curveCount === CURVE_POINTS)
						throw new Error("Display curve point capacity");
					xy[2 * curveCount] = point.xE7;
					xy[2 * curveCount + 1] = point.yE7;
					prefixes[2 * curveCount] = point.forward;
					prefixes[2 * curveCount + 1] = point.backward;
					curveCount++;
				});
				visit(arc, earliest);
			}
		}
	};
	const envelope = [Infinity, Infinity, -Infinity, -Infinity];
	const expand = (point: Coordinate, meters: number) => {
		const angular = meters / EARTH_METERS;
		const dy = angular / RAD;
		const dx =
			Math.abs(point[1]) + dy >= 90
				? 180
				: Math.asin(Math.min(1, Math.sin(angular) / Math.cos(point[1] * RAD))) /
					RAD;
		envelope[0] = Math.min(envelope[0], point[0] - dx);
		envelope[1] = Math.min(envelope[1], point[1] - dy);
		envelope[2] = Math.max(envelope[2], point[0] + dx);
		envelope[3] = Math.max(envelope[3], point[1] + dy);
	};
	expand(connection.origin, (horizon * 25) / 3.6);
	activeSpans((_arc, earliest) => {
		const radius = (((field.horizonTicks - earliest) / 8) * 25) / 3.6;
		for (let i = 1; i < curveCount; i++) {
			const a = pointAt(i - 1),
				b = pointAt(i),
				padded = radius + sphericalDistance(a, b) / 2;
			expand(a, padded);
			expand(b, padded);
		}
	});
	envelope[0] = Math.max(envelope[0], geography.bounds[0]);
	envelope[1] = Math.max(envelope[1], geography.bounds[1]);
	envelope[2] = Math.min(envelope[2], geography.bounds[2]);
	envelope[3] = Math.min(envelope[3], geography.bounds[3]);
	if (envelope[0] > envelope[2] || envelope[1] > envelope[3])
		throw new Error("Display envelope outside geography");
	const envelopeMs = performance.now() - began;
	let step = 5000;
	while (
		makeFrame(envelope, step).width * makeFrame(envelope, step).height >
			limits.cells &&
		step < 25000
	)
		step++;
	const retries: { stepDegrees: number; reason: string }[] = [];
	for (let attempt = 0; attempt < 9; attempt++) {
		const frame = makeFrame(envelope, step),
			count = frame.width * frame.height;
		if (
			count > limits.cells ||
			frame.width > maxWidth ||
			frame.height > maxHeight
		)
			throw new Error("Display frame capacity");
		const started = performance.now();
		try {
			times.fill(UNREACHED_SECONDS);
			parents.fill(255);
			coverage.fill(0);
			rasterLand(frame, geography, land, boundary, row, check);
			rasterLinks(frame, geography, land, boundary, links, check);
			const vertical = localCosts(frame, horizontal, diagonal),
				maskMs = performance.now() - started;
			const seed = (
				point: Coordinate,
				arrivalTicks: number | null,
				kind: number,
			) => {
				if (arrivalTicks === null || arrivalTicks > field.horizonTicks) return;
				const i = cellAt(frame, point);
				if (i < 0) return;
				setBit(coverage, i);
				if (!bit(land, i)) return;
				const target = center(frame, i);
				const candidate =
					Math.ceil(arrivalTicks / 8) +
					Math.ceil(connectorPrice(point, target).ticks / 8);
				if (candidate > horizon || candidate >= times[i]) return;
				if (bit(boundary, i) && !landConnection(geography, [...point], target))
					return;
				times[i] = candidate;
				setNibble(parents, i, kind);
			};
			seed(connection.origin, 0, 9);
			let samples = 0,
				active = 0;
			const spacing =
				((step / 1e6) *
					RAD *
					EARTH_METERS *
					Math.cos(
						Math.max(
							Math.abs(geography.bounds[1]),
							Math.abs(geography.bounds[3]),
						) * RAD,
					)) /
				2;
			activeSpans((arc) => {
				active++;
				const visit = (
					segment: number,
					fraction: number,
					coordinate: Coordinate,
				) => {
					if (++samples > 30000000)
						throw new Error("Display road sample capacity");
					if ((samples & 65535) === 0) check();
					seed(
						coordinate,
						arrivalAtAccessProgress(graph, field, {
							canonicalArc: arc,
							rank: segment + fraction,
							lastRank: curveCount - 1,
							forwardUnits:
								prefixes[2 * segment] +
								fraction * (prefixes[2 * segment + 2] - prefixes[2 * segment]),
							backwardUnits:
								prefixes[2 * segment + 1] +
								fraction *
									(prefixes[2 * segment + 3] - prefixes[2 * segment + 1]),
						}),
						8,
					);
				};
				for (let segment = 0; segment < curveCount - 1; segment++) {
					const a = pointAt(segment),
						b = pointAt(segment + 1);
					const parts = Math.max(
						1,
						Math.ceil(sphericalDistance(a, b) / spacing),
					);
					for (let j = 0; j <= parts; j++)
						visit(segment, j / parts, roadCoordinate(a, b, j / parts));
					for (
						let seed = field.seeds.firstByArc.get(arc) ?? -1;
						seed !== -1;
						seed = field.seeds.next[seed]
					) {
						const rank = field.seeds.rank[seed];
						if (rank >= segment && rank <= segment + 1)
							visit(
								segment,
								rank - segment,
								roadCoordinate(a, b, rank - segment),
							);
					}
				}
			});
			const seedMs = performance.now() - started - maskMs;
			heap.length = 0;
			heap.peak = 0;
			let settles: number;
			try {
				settles = fillLocal(
					frame,
					times,
					parents,
					links,
					horizontal,
					diagonal,
					vertical,
					horizon,
					heap,
					check,
				);
			} finally {
				if (borrowed) restoreAccessVertices(graph, field);
			}
			const fillMs = performance.now() - started - maskMs - seedMs;
			options.probe?.({
				frame,
				times: times.subarray(0, count),
				parents,
				links,
				land,
				coverage,
				boundary,
				horizontal,
				diagonal,
				vertical,
			});
			const mask = new Uint8Array(raster, 0, count);
			let selectedCells = 0,
				localCells = 0,
				roadOnlyCells = 0;
			for (let i = 0; i < count; i++) {
				const local = times[i] <= horizon,
					covered = bit(coverage, i) !== 0;
				if (local) localCells++;
				else if (covered) roadOnlyCells++;
				mask[i] = local || covered ? 1 : 0;
				selectedCells += mask[i];
			}
			const edges = new Uint8Array(
				raster,
				count,
				(frame.width + 1) * (frame.height + 1),
			);
			const contours = boundedContours(
				mask,
				edges,
				frame,
				limits.limits,
				check,
				geography.bounds,
			);
			const output = {
				type: "MultiPolygon" as const,
				coordinates: contours.polygons,
			};
			const jsonBytes = Buffer.byteLength(JSON.stringify(output));
			if (jsonBytes > limits.json)
				throw new DisplayLimit("output JSON capacity");
			return {
				output,
				frame,
				stats: {
					envelopeMs,
					maskMs,
					seedMs,
					fillMs,
					contourMs: performance.now() - started - maskMs - seedMs - fillMs,
					displayMs: performance.now() - began,
					maximumBackingBufferBytes: scratch,
					borrowedVertexWorkspace: borrowed,
					samples,
					activeSpans: active,
					settles,
					maximumHeapEntries: heap.peak,
					selectedCells,
					localCells,
					roadOnlyCells,
					edges: contours.edgeCount,
					rings: contours.rings,
					vertices: contours.vertices,
					jsonBytes,
					retries,
				},
			};
		} catch (error) {
			if (!(error instanceof DisplayLimit)) throw error;
			retries.push({ stepDegrees: step / 1e6, reason: error.message });
			if (step === 25000 || attempt === 8) throw error;
			step = Math.min(25000, Math.ceil(step * 1.25));
		}
	}
	throw new Error("Display attempt bound");
}

export function accessFilledDisplay(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	connection: OriginConnection,
	field: AccessRoadField,
	options: DisplayOptions = {},
) {
	return renderAccess(
		graph,
		geometry,
		geography,
		connection,
		field,
		options,
		345600,
	);
}
export function diagnosticAccessFilledDisplay(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	connection: OriginConnection,
	field: AccessRoadField,
	options: DisplayOptions = {},
) {
	return renderAccess(
		graph,
		geometry,
		geography,
		connection,
		field,
		options,
		432000,
	);
}
