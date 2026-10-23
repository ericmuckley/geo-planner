import type { Origin } from "../lib/reachability";
import { cellContours, containsPolygon } from "./coarse-contours";
import { landConnection } from "./coarse-geography";

export type RoadVisit = {
	speedKph: number;
	anchorIndex: number;
	points: number[][];
	cumulativeKm: number[];
	transferKm?: number;
};

export type RoadVisits = Iterable<[number, RoadVisit]> & {
	readonly size: number;
	get(cell: number): RoadVisit | undefined;
};

export type GridAttachment = {
	cell: number;
	distanceKm: number;
	minutes: number;
	roadKm?: number;
};

export type GridData = {
	bounds: number[];
	width: number;
	height: number;
	step: number;
	localSpeedKph: number;
	land: Uint8Array;
	traversable: Uint8Array;
	links: Uint8Array;
	roadDeciseconds?: Uint16Array;
	displayLand?: Uint8Array;
	anchorOffsets?: Int16Array;
	shoreLinks?: Uint8Array;
	roadAccess?: number[][];
	roadVisits?: RoadVisits;
	supplementalRoadVisits?: RoadVisits;
	roadLayer?: {
		anchorOffsets: Int16Array;
		roadDeciseconds: Uint16Array;
		transferDeciseconds: Uint16Array;
	};
	boundary: number[][][][];
	lakes: number[][][][];
};

const radians = Math.PI / 180;
export function distanceKm(a: number[], b: number[]) {
	const lat = (b[1] - a[1]) * radians;
	const lon = (b[0] - a[0]) * radians;
	const h =
		Math.sin(lat / 2) ** 2 +
		Math.cos(a[1] * radians) *
			Math.cos(b[1] * radians) *
			Math.sin(lon / 2) ** 2;
	return 12_742 * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function gridPosition(grid: GridData, cell: number) {
	const size = grid.width * grid.height;
	const offsets =
		cell >= size && grid.roadLayer
			? grid.roadLayer.anchorOffsets
			: grid.anchorOffsets;
	if (cell >= size && grid.roadLayer) cell -= size;
	return [
		grid.bounds[0] +
			((cell % grid.width) + 0.5) * grid.step +
			(offsets?.[cell * 2] ?? 0) / 100000,
		grid.bounds[1] +
			(Math.floor(cell / grid.width) + 0.5) * grid.step +
			(offsets?.[cell * 2 + 1] ?? 0) / 100000,
	];
}

export function gridCellMinutes(
	grid: GridData,
	labels: Float64Array,
	cell: number,
) {
	return grid.roadLayer
		? Math.min(labels[cell], labels[grid.width * grid.height + cell])
		: labels[cell];
}

function nearBoundary(point: [number, number], polygon: number[][][]) {
	const scale = Math.cos(point[1] * radians);
	for (const ring of polygon) {
		for (let i = 1; i < ring.length; i++) {
			const a = ring[i - 1];
			const b = ring[i];
			if (
				point[1] < Math.min(a[1], b[1]) - 0.01 ||
				point[1] > Math.max(a[1], b[1]) + 0.01 ||
				point[0] < Math.min(a[0], b[0]) - 0.02 ||
				point[0] > Math.max(a[0], b[0]) + 0.02
			)
				continue;
			const dx = (b[0] - a[0]) * scale;
			const dy = b[1] - a[1];
			const length = dx * dx + dy * dy;
			const t = length
				? Math.max(
						0,
						Math.min(
							1,
							((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) /
								length,
						),
					)
				: 0;
			if (distanceKm(point, [a[0] + (b[0] - a[0]) * t, a[1] + dy * t]) <= 1)
				return true;
		}
	}
	return false;
}

class Queue {
	private cells: number[] = [];
	private costs: number[] = [];
	get length() {
		return this.cells.length;
	}
	push(cell: number, cost: number) {
		let index = this.cells.length;
		this.cells.push(cell);
		this.costs.push(cost);
		while (index > 0) {
			const parent = (index - 1) >> 1;
			if (this.costs[parent] <= cost) break;
			this.cells[index] = this.cells[parent];
			this.costs[index] = this.costs[parent];
			index = parent;
		}
		this.cells[index] = cell;
		this.costs[index] = cost;
	}
	pop(): [number, number] {
		const result: [number, number] = [this.cells[0], this.costs[0]];
		const lastCell = this.cells.pop();
		const lastCost = this.costs.pop();
		if (this.cells.length && lastCell !== undefined && lastCost !== undefined) {
			let index = 0;
			while (index * 2 + 1 < this.cells.length) {
				let child = index * 2 + 1;
				if (
					child + 1 < this.cells.length &&
					this.costs[child + 1] < this.costs[child]
				)
					child++;
				if (this.costs[child] >= lastCost) break;
				this.cells[index] = this.cells[child];
				this.costs[index] = this.costs[child];
				index = child;
			}
			this.cells[index] = lastCell;
			this.costs[index] = lastCost;
		}
		return result;
	}
}

const directions = [
	[1, 0],
	[1, 1],
	[0, 1],
	[-1, 1],
	[-1, 0],
	[-1, -1],
	[0, -1],
	[1, -1],
];

export function gridAttachments(
	grid: GridData,
	origin: Origin,
): GridAttachment[] {
	const x = Math.floor((origin.lon - grid.bounds[0]) / grid.step);
	const y = Math.floor((origin.lat - grid.bounds[1]) / grid.step);
	if (x < 0 || x >= grid.width || y < 0 || y >= grid.height) return [];
	const cell = y * grid.width + x;
	const point = [origin.lon, origin.lat];
	const candidate = (target: number) => {
		const km = distanceKm(point, gridPosition(grid, target));
		return {
			cell: target,
			distanceKm: km,
			minutes: (km / grid.localSpeedKph) * 60,
		};
	};
	if (!grid.shoreLinks) return [candidate(cell)];
	const supported = (attachment: { cell: number; distanceKm: number }) =>
		grid.traversable[attachment.cell] &&
		landConnection(
			grid,
			point,
			gridPosition(grid, attachment.cell),
			1 / Math.max(attachment.distanceKm, 1),
		);
	const own = candidate(cell);
	const ownSupported = supported(own);
	if (ownSupported && !grid.roadVisits && !grid.supplementalRoadVisits)
		return [own];
	// An adjacent representative is usable only with a continuous land connection.
	// A known island cannot attach across even a narrow channel to the mainland.
	const neighborCells = directions.flatMap(([dx, dy]) => {
		const xx = x + dx,
			yy = y + dy;
		return xx >= 0 && xx < grid.width && yy >= 0 && yy < grid.height
			? [yy * grid.width + xx]
			: [];
	});
	const nearby: GridAttachment[] = ownSupported
		? [own]
		: neighborCells.map(candidate).filter(supported);
	const cells = new Set([cell, ...neighborCells]);
	for (const [target, lon, lat, roadKm] of grid.roadAccess ?? []) {
		if (ownSupported || !cells.has(target)) continue;
		const localKm = distanceKm(point, [lon, lat]);
		if (landConnection(grid, point, [lon, lat], 1 / Math.max(localKm, 1)))
			nearby.push({
				cell: target,
				distanceKm: localKm + roadKm,
				minutes: ((localKm + roadKm) / grid.localSpeedKph) * 60,
			});
	}
	const visit = grid.roadVisits?.get(cell);
	if (visit) nearby.push(...roadAttachments(grid, point, cell, visit));
	const supplemental = grid.supplementalRoadVisits?.get(cell);
	if (supplemental)
		nearby.push(...roadAttachments(grid, point, cell, supplemental));
	if (supplemental && grid.roadLayer?.transferDeciseconds[cell])
		nearby.push(
			...roadAttachments(grid, point, grid.width * grid.height + cell, {
				...supplemental,
				transferKm: 0,
			}),
		);
	const best = new Map<number, GridAttachment>();
	for (const attachment of nearby)
		if (attachment.minutes < (best.get(attachment.cell)?.minutes ?? Infinity))
			best.set(attachment.cell, attachment);
	return [...best.values()].sort((a, b) => a.minutes - b.minutes);
}

function roadAttachments(
	grid: GridData,
	point: number[],
	cell: number,
	visit: RoadVisit,
): GridAttachment[] {
	const result: Array<
		GridAttachment & { projected: number[]; localKm: number }
	> = [];
	const scale = Math.cos(point[1] * radians);
	for (let i = 1; i < visit.points.length; i++) {
		const a = visit.points[i - 1],
			b = visit.points[i];
		const dx = (b[0] - a[0]) * scale,
			dy = b[1] - a[1];
		const length = dx * dx + dy * dy;
		const t = length
			? Math.max(
					0,
					Math.min(
						1,
						((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) / length,
					),
				)
			: 0;
		// Endpoints remain candidates when the nearest projection is generalized
		// water or its local connector crosses a channel. Only the retained road
		// geometry may cross water between the access point and canonical anchor.
		for (const part of new Set([0, t, 1])) {
			const projected = [a[0] + (b[0] - a[0]) * part, a[1] + dy * part];
			const localKm = distanceKm(point, projected);
			const roadKm =
				i <= visit.anchorIndex
					? visit.cumulativeKm[visit.anchorIndex] -
						visit.cumulativeKm[i] +
						distanceKm(projected, b)
					: visit.cumulativeKm[i - 1] -
						visit.cumulativeKm[visit.anchorIndex] +
						distanceKm(a, projected);
			result.push({
				projected,
				localKm,
				cell,
				distanceKm: localKm + roadKm + (visit.transferKm ?? 0),
				minutes:
					Math.ceil(
						((localKm + (visit.transferKm ?? 0)) / grid.localSpeedKph +
							roadKm / visit.speedKph) *
							36000,
					) / 600,
				roadKm,
			});
		}
	}
	// Only the cheapest valid attachment to this cell can survive. Checking in
	// cost order avoids thousands of polygon scans for dense source geometry.
	result.sort((a, b) => a.minutes - b.minutes);
	for (const { projected, localKm, ...attachment } of result)
		if (landConnection(grid, point, projected, 1 / Math.max(localKm, 1)))
			return [attachment];
	return [];
}

export function attachGrid(grid: GridData, origin: Origin) {
	return gridAttachments(grid, origin)[0];
}

// Base states are cell indices. Census states are size + cell, connected only
// by explicit source-road links and positive, paid transfers to the base state.
export function* gridTransitions(
	grid: GridData,
	node: number,
	lengths?: number[][],
) {
	const { width, height, roadLayer } = grid;
	const size = width * height;
	const inRoadLayer = node >= size;
	const cell = inRoadLayer ? node - size : node;
	const transfer = roadLayer?.transferDeciseconds[cell];
	if (transfer)
		yield {
			cell: node,
			target: inRoadLayer ? cell : size + cell,
			minutes: transfer / 600,
			kind: "transfer" as const,
		};
	const x = cell % width,
		y = Math.floor(cell / width);
	for (let d = 0; d < directions.length; d++) {
		const [dx, dy] = directions[d];
		const xx = x + dx,
			yy = y + dy;
		if (xx < 0 || xx >= width || yy < 0 || yy >= height) continue;
		const target = yy * width + xx;
		const link = d < 4 ? cell * 4 + d : target * 4 + d - 4;
		if (inRoadLayer) {
			const time = roadLayer?.roadDeciseconds[link];
			if (time)
				yield {
					cell: node,
					target: size + target,
					minutes: time / 600,
					kind: "road" as const,
				};
			continue;
		}
		if (!grid.traversable[target]) continue;
		const overland =
			!!((grid.shoreLinks?.[Math.floor(link / 4)] ?? 0) & (1 << (link % 4))) ||
			(grid.land[cell] &&
				grid.land[target] &&
				(!dx ||
					!dy ||
					(grid.land[y * width + xx] && grid.land[yy * width + x])));
		const length =
			lengths?.[y][d] ??
			distanceKm(
				[
					grid.bounds[0] + 0.5 * grid.step,
					grid.bounds[1] + (y + 0.5) * grid.step,
				],
				[
					grid.bounds[0] + (dx + 0.5) * grid.step,
					grid.bounds[1] + (y + dy + 0.5) * grid.step,
				],
			);
		const roadMinutes = grid.roadDeciseconds
			? (grid.roadDeciseconds[link] || Infinity) / 600
			: grid.links[link]
				? (length / grid.links[link]) * 60
				: Infinity;
		const localMinutes = overland
			? ((grid.anchorOffsets
					? distanceKm(gridPosition(grid, cell), gridPosition(grid, target))
					: length) /
					grid.localSpeedKph) *
				60
			: Infinity;
		const minutes = Math.min(roadMinutes, localMinutes);
		if (Number.isFinite(minutes))
			yield {
				cell: node,
				target,
				minutes,
				kind:
					roadMinutes <= localMinutes ? ("road" as const) : ("local" as const),
			};
	}
}

export function estimateGrid(grid: GridData, origin: Origin, budget: number) {
	const started = performance.now();
	const point: [number, number] = [origin.lon, origin.lat];
	if (
		!grid.boundary.some(
			(polygon) =>
				containsPolygon(point, polygon) || nearBoundary(point, polygon),
		) ||
		grid.lakes.some(
			(polygon) =>
				containsPolygon(point, polygon) && !nearBoundary(point, polygon),
		)
	)
		throw new RangeError(
			"Choose a land location in the contiguous United States.",
		);
	const [west, south] = grid.bounds;
	const { width, height, step } = grid;
	const center = (x: number, y: number) => [
		west + (x + 0.5) * step,
		south + (y + 0.5) * step,
	];
	const x = Math.floor((origin.lon - west) / step);
	const y = Math.floor((origin.lat - south) / step);
	const labels = new Float64Array(
		width * height * (grid.roadLayer ? 2 : 1),
	).fill(Infinity);
	const queue = new Queue();
	if (x < 0 || x >= width || y < 0 || y >= height)
		throw new RangeError("Choose a location within the contiguous US grid.");
	const seed = y * width + x;
	// Retain legacy seed activation for v1/v2 comparison. V3 uses checked input
	// access and keeps shared land/traversal masks unchanged.
	const land =
		grid.shoreLinks || grid.land[seed] ? grid.land : grid.land.slice();
	const traversable =
		grid.shoreLinks || grid.traversable[seed]
			? grid.traversable
			: grid.traversable.slice();
	if (!grid.shoreLinks) land[seed] = traversable[seed] = 1;
	const searchGrid =
		land === grid.land && traversable === grid.traversable
			? grid
			: { ...grid, land, traversable };
	const attachments = gridAttachments(grid, origin);
	const attachmentKm = attachments[0]?.distanceKm ?? 0;
	// Seed every supported fallback: the nearest land patch may be a dead end
	// while a slightly longer explicit bridge access reaches the road network.
	for (const attachment of attachments) {
		const initialCost = attachment.minutes;
		labels[attachment.cell] = initialCost;
		queue.push(attachment.cell, initialCost);
	}
	if (!attachments.length) labels[seed] = 0; // Display an isolated input cell without expanding it.
	// Distances depend on latitude and direction, not longitude. Compute once per row.
	const lengths = Array.from({ length: height }, (_, row) =>
		directions.map(([dx, dy]) =>
			distanceKm(center(0, row), center(dx, row + dy)),
		),
	);
	let settled = 0;
	while (queue.length) {
		const [cell, cost] = queue.pop();
		if (cost !== labels[cell]) continue;
		if (cost > budget) break;
		settled++;
		for (const { target, minutes } of gridTransitions(
			searchGrid,
			cell,
			lengths,
		)) {
			const next = cost + minutes;
			if (next <= budget && next < labels[target]) {
				labels[target] = next;
				queue.push(target, next);
			}
		}
	}
	const searchMs = performance.now() - started;
	const mask = new Uint8Array(width * height);
	let reachedCells = 0;
	for (let i = 0; i < width * height; i++) {
		if (
			(i === seed && grid.shoreLinks) ||
			((i === seed || (grid.displayLand ?? land)[i]) &&
				gridCellMinutes(grid, labels, i) <= budget)
		) {
			mask[i] = 1;
			reachedCells++;
		}
	}
	const coordinates = cellContours(mask, width, height, west, south, step);
	if (!coordinates.length)
		throw new RangeError("Choose a longer budget for this coarse-grid origin.");
	return {
		coordinates,
		labels,
		reachedCells,
		settled,
		attachmentKm,
		searchMs,
		contourMs: performance.now() - started - searchMs,
	};
}
