/** Consume a privately scoped road query, reusing its buffers after all road seeding. */
import {
	type AccessRoadField,
	type AccessStart,
	accessArcEntryTicks,
	arrivalAtAccessProgress,
} from "./coarse_osm_access_road_field_v1.ts";
import {
	withAccessContextRoadField,
	withDiagnosticContextRoadField,
} from "./coarse_osm_context_road_field_v1.ts";
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
} from "./coarse_osm_display_grid_v3.ts";
import {
	type DisplayOptions,
	roadCoordinate,
} from "./coarse_osm_filled_display_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v2.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import { reusedDisplayBytes } from "./coarse_osm_reused_display_budget_v1.ts";
import { UNREACHED_SECONDS } from "./coarse_osm_road_field_v1.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import {
	type Coordinate,
	EARTH_METERS,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import { DISPLAY_CAP_BYTES } from "./coarse_osm_split_display_budget_v1.ts";
import type { TurnContexts } from "./coarse_osm_turn_contexts_v1.ts";

const CURVE_POINTS = 4096;
const RAD = Math.PI / 180;
const LIMITS: ContourLimits = { edges: 400000, rings: 4096, vertices: 100000 };
// Valid seconds end at 54000. These temporary states preserve road coverage before masks exist.
const COVERED_BLOCKED = 65534;
const COVERED_LATE = 65533;
export type ReusedDisplayOptions = DisplayOptions & {
	maxTicks?: number;
	observeBacking?: (buffers: ArrayBufferLike[]) => void;
	/** Diagnostic preparation may retain scalar summaries, never borrowed buffers. */
	beforeSeed?: (field: AccessRoadField) => void;
};

function consumeField(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	connection: OriginConnection,
	initialField: AccessRoadField,
	options: ReusedDisplayOptions,
) {
	let field: AccessRoadField | null = initialField;
	let xy = new Int32Array(0);
	let prefixes = new Uint16Array(0);
	let times = new Uint16Array(0);
	let masks: ArrayBufferLike = new ArrayBuffer(0);
	let labelBuffer: ArrayBufferLike = new ArrayBuffer(0);
	let vertexBuffer: ArrayBufferLike = new ArrayBuffer(0);
	let raster = new ArrayBuffer(0);
	const readField = () => {
		if (field === null) throw new Error("Road field has been consumed");
		return field;
	};
	try {
		const began = performance.now();
		const check = options.check ?? (() => {});
		const heapEntries = options.heapEntries ?? 1000000;
		const maxCells = options.maxCells ?? 33554432;
		const maxJson = options.maxJsonBytes ?? 3000000;
		const contourLimits = options.contourLimits ?? LIMITS;
		for (const [value, maximum] of [
			[heapEntries, 1000000],
			[maxCells, 33554432],
			[maxJson, 3000000],
			[contourLimits.edges, LIMITS.edges],
			[contourLimits.rings, LIMITS.rings],
			[contourLimits.vertices, LIMITS.vertices],
		])
			if (!Number.isSafeInteger(value) || value < 1 || value > maximum)
				throw new Error("Reused display option domain");
		if (
			readField().labels.length !== graph.arcs ||
			readField().vertexArrivalSeconds.length !== graph.vertices ||
			readField().horizonTicks > 432000 ||
			readField().source.initialTicks !== connection.connectorTicks ||
			readField().source.canonicalArc !== connection.snap.canonicalArc ||
			readField().labels.byteOffset !== 0 ||
			readField().vertexArrivalSeconds.byteOffset !== 0
		)
			throw new Error("Reused display field/source mismatch");
		options.beforeSeed?.(readField());
		const fieldStats = { ...readField().stats };
		labelBuffer = readField().labels.buffer;
		vertexBuffer = readField().vertexArrivalSeconds.buffer;
		const labelBytes = readField().labels.byteLength;
		const vertexBytes = readField().vertexArrivalSeconds.byteLength;
		const horizon = Math.floor(readField().horizonTicks / 8);
		xy = new Int32Array(2 * CURVE_POINTS);
		prefixes = new Uint16Array(2 * CURVE_POINTS);
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
						if (readField().vertexArrivalSeconds[vertex] !== UNREACHED_SECONDS)
							earliest = Math.min(
								earliest,
								Math.max(0, readField().vertexArrivalSeconds[vertex] * 8 - 7),
							);
					if (readField().labels[arc] !== 0xffffffff)
						earliest = Math.min(
							earliest,
							accessArcEntryTicks(graph, readField(), arc) ?? Infinity,
						);
					if (reverse !== null && readField().labels[reverse] !== 0xffffffff)
						earliest = Math.min(
							earliest,
							accessArcEntryTicks(graph, readField(), reverse) ?? Infinity,
						);
					earliest = Math.min(earliest, readField().seeds.earliest(arc));
					if (earliest > readField().horizonTicks) continue;
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
					: Math.asin(
							Math.min(1, Math.sin(angular) / Math.cos(point[1] * RAD)),
						) / RAD;
			envelope[0] = Math.min(envelope[0], point[0] - dx);
			envelope[1] = Math.min(envelope[1], point[1] - dy);
			envelope[2] = Math.max(envelope[2], point[0] + dx);
			envelope[3] = Math.max(envelope[3], point[1] + dy);
		};
		expand(connection.origin, (horizon * 25) / 3.6);
		activeSpans((_arc, earliest) => {
			const radius = (((readField().horizonTicks - earliest) / 8) * 25) / 3.6;
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
		let frame = makeFrame(envelope, step);
		const input = () => ({
			fieldPeakBytes: fieldStats.maximumBackingBufferBytes,
			labelBytes,
			vertexBytes,
			maxWidth: frame.width,
			maxHeight: frame.height,
			heapEntries,
		});
		let sizes = reusedDisplayBytes(input(), frame.width * frame.height);
		while (
			frame.width * frame.height > maxCells ||
			Math.max(sizes.seed, sizes.fill) > DISPLAY_CAP_BYTES
		) {
			if (++step > 25000) throw new Error("Reused display frame capacity");
			frame = makeFrame(envelope, step);
			sizes = reusedDisplayBytes(input(), frame.width * frame.height);
		}
		check();
		const count = frame.width * frame.height;
		raster = new ArrayBuffer(2 * count + frame.width + frame.height + 1);
		times = new Uint16Array(raster, 0, count).fill(UNREACHED_SECONDS);
		let originCell = -1;
		let originCandidate = Infinity;
		const seed = (
			point: Coordinate,
			arrivalTicks: number | null,
			kind: number,
		) => {
			if (arrivalTicks === null || arrivalTicks > readField().horizonTicks)
				return;
			const i = cellAt(frame, point);
			if (i < 0) return;
			const target = center(frame, i);
			if (times[i] === UNREACHED_SECONDS)
				times[i] = landConnection(geography, target, target)
					? COVERED_LATE
					: COVERED_BLOCKED;
			if (times[i] === COVERED_BLOCKED) return;
			const candidate =
				Math.ceil(arrivalTicks / 8) +
				Math.ceil(connectorPrice(point, target).ticks / 8);
			if (
				candidate > horizon ||
				candidate >= times[i] ||
				!landConnection(geography, [...point], target)
			)
				return;
			times[i] = candidate;
			if (kind === 9) {
				originCell = i;
				originCandidate = candidate;
			}
		};
		seed(connection.origin, 0, 9);
		let samples = 0;
		let active = 0;
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
					throw new Error("Reused display road sample capacity");
				if ((samples & 65535) === 0) check();
				seed(
					coordinate,
					arrivalAtAccessProgress(graph, readField(), {
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
				const parts = Math.max(1, Math.ceil(sphericalDistance(a, b) / spacing));
				for (let j = 0; j <= parts; j++)
					visit(segment, j / parts, roadCoordinate(a, b, j / parts));
				for (
					let at = readField().seeds.firstByArc.get(arc) ?? -1;
					at !== -1;
					at = readField().seeds.next[at]
				) {
					const rank = readField().seeds.rank[at];
					if (rank >= segment && rank <= segment + 1)
						visit(
							segment,
							rank - segment,
							roadCoordinate(a, b, rank - segment),
						);
				}
			}
		});
		const seedMs = performance.now() - began - envelopeMs;
		options.observeBacking?.([
			labelBuffer,
			vertexBuffer,
			xy.buffer,
			prefixes.buffer,
			raster,
			readField().seeds.buffer,
		]);
		// All source queries have finished. The private loan may now be consumed; no buffers escape it.
		readField().labels = new Uint32Array(0);
		readField().vertexArrivalSeconds = new Uint16Array(0);
		field = null;
		masks = sizes.extraMasks ? new ArrayBuffer(sizes.masks) : labelBuffer;
		let offset = 0;
		const bytes = (length: number) => {
			const result = new Uint8Array(masks, offset, length);
			offset += length;
			return result;
		};
		const shorts = (length: number) => {
			const result = new Uint16Array(masks, offset, length);
			offset += 2 * length;
			return result;
		};
		const bitBytes = Math.ceil(count / 8);
		const nibbleBytes = Math.ceil(count / 2);
		const land = bytes(bitBytes);
		const boundary = bytes(bitBytes);
		const countryBoundary = bytes(bitBytes);
		const coverage = bytes(bitBytes);
		const parents = bytes(nibbleBytes);
		const links = bytes(nibbleBytes);
		const row = bytes(2 * frame.width);
		const horizontal = shorts(frame.height);
		const diagonal = shorts(frame.height);
		if (offset !== sizes.masks) throw new Error("Reused display mask layout");
		coverage.fill(0);
		parents.fill(255);
		const queue = sizes.extraQueue
			? new ArrayBuffer(sizes.extraQueue)
			: vertexBuffer;
		options.observeBacking?.([masks, queue]);
		const heap = new DisplayQueue(
			new Uint32Array(queue, 0, heapEntries),
			new Uint32Array(queue, 4 * heapEntries, heapEntries),
		);
		const started = performance.now();
		rasterLand(frame, geography, land, boundary, row, check, countryBoundary);
		rasterLinks(
			frame,
			geography,
			land,
			boundary,
			links,
			check,
			countryBoundary,
		);
		const vertical = localCosts(frame, horizontal, diagonal);
		for (let i = 0; i < count; i++) {
			const value = times[i];
			if (value === UNREACHED_SECONDS) continue;
			setBit(coverage, i);
			if ((value !== COVERED_BLOCKED) !== Boolean(bit(land, i)))
				throw new Error(
					"Reused display center policy differs from raster mask",
				);
			if (value === COVERED_BLOCKED || value === COVERED_LATE)
				times[i] = UNREACHED_SECONDS;
			else
				setNibble(
					parents,
					i,
					i === originCell && value === originCandidate ? 9 : 8,
				);
		}
		const maskMs = performance.now() - started;
		const settles = fillLocal(
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
		const fillMs = performance.now() - started - maskMs;
		options.probe?.({
			frame,
			times,
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
		let localCells = 0,
			roadOnlyCells = 0,
			selectedCells = 0;
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
			contourLimits,
			check,
			geography.bounds,
		);
		const output = {
			type: "MultiPolygon" as const,
			coordinates: contours.polygons,
		};
		const jsonBytes = Buffer.byteLength(JSON.stringify(output));
		if (jsonBytes > maxJson)
			throw new DisplayLimit("Reused display JSON capacity");
		return {
			output,
			frame,
			fieldStats,
			stats: {
				envelopeMs,
				seedMs,
				maskMs,
				fillMs,
				contourMs: performance.now() - started - maskMs - fillMs,
				displayMs: performance.now() - began,
				maximumBackingBufferBytes: Math.max(sizes.seed, sizes.fill),
				seedPhaseDeclaredBytes: sizes.seed,
				fillPhaseDeclaredBytes: sizes.fill,
				reusedLabelBytes: sizes.extraMasks ? 0 : labelBytes,
				reusedVertexBytes: sizes.extraQueue ? 0 : vertexBytes,
				samples,
				activeSpans: active,
				settles,
				maximumHeapEntries: heap.peak,
				localCells,
				roadOnlyCells,
				selectedCells,
				edges: contours.edgeCount,
				rings: contours.rings,
				vertices: contours.vertices,
				jsonBytes,
				retries: [],
			},
		};
	} finally {
		// Closures share this context; sever its buffer aliases on success and failure.
		field = null;
		xy = new Int32Array(0);
		prefixes = new Uint16Array(0);
		times = new Uint16Array(0);
		masks = new ArrayBuffer(0);
		labelBuffer = new ArrayBuffer(0);
		vertexBuffer = new ArrayBuffer(0);
		raster = new ArrayBuffer(0);
	}
}

/** Own the entire query loan so callers cannot reuse consumed road labels. */
export function reusedContextDisplay(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	contexts: TurnContexts,
	geography: OriginGeography,
	connection: OriginConnection,
	starts: AccessStart[],
	options: ReusedDisplayOptions = {},
	diagnostic = false,
) {
	const withField = diagnostic
		? withDiagnosticContextRoadField
		: withAccessContextRoadField;
	return withField(
		graph,
		geometry,
		contexts,
		starts,
		(field) =>
			consumeField(graph, geometry, geography, connection, field, options),
		{
			maxTicks: options.maxTicks,
			maxHeapEntries: options.heapEntries,
			check: options.check,
		},
	);
}
