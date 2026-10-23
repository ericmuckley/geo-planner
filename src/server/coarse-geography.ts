import { containsPolygon } from "./coarse-contours";

type Geography = { boundary: number[][][][]; lakes: number[][][][] };

type IndexedRing = {
	points: number[][];
	firstBand: number;
	bands: Uint32Array[];
	west: number;
	east: number;
	roundingGuard: number;
};
type IndexedPolygon = IndexedRing[];
const indexes = new WeakMap<
	Geography,
	{
		boundary: IndexedPolygon[];
		lakes: IndexedPolygon[];
		rings: IndexedRing[];
		sourceBoundary: Geography["boundary"];
		sourceLakes: Geography["lakes"];
	}
>();
const band = (latitude: number) => Math.floor(latitude * 100);

// Bundled geography is immutable. Index edge candidates, never query results;
// the original coordinates and intersection arithmetic remain unchanged.
export function prepareGeography(geography: Geography) {
	const polygons = (source: number[][][][]) => {
		const indexed = source.map((polygon) => {
			const rings = polygon.map((points) => {
				let firstBand = Infinity;
				let lastBand = -Infinity;
				let west = Infinity;
				let east = -Infinity;
				for (const point of points) {
					firstBand = Math.min(firstBand, band(point[1]));
					lastBand = Math.max(lastBand, band(point[1]));
					west = Math.min(west, point[0]);
					east = Math.max(east, point[0]);
					Object.freeze(point);
				}
				const bands = Array.from(
					{ length: lastBand - firstBand + 1 },
					() => [] as number[],
				);
				for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
					const low = band(Math.min(points[i][1], points[j][1]));
					const high = band(Math.max(points[i][1], points[j][1]));
					for (let y = low; y <= high; y++) bands[y - firstBand].push(i);
				}
				const edgeEast = (i: number) =>
					Math.max(points[i][0], points[i ? i - 1 : points.length - 1][0]);
				const packedBands = bands.map((candidates) =>
					Uint32Array.from(
						candidates.sort((a, b) => edgeEast(b) - edgeEast(a)),
					),
				);
				// Conservative candidate bounds only; exact geometry checks still decide
				// membership. Cover floating-point interpolation rounding at vertices.
				const roundingGuard =
					Number.EPSILON * Math.max(1, Math.abs(west), Math.abs(east)) * 16;
				Object.freeze(points);
				return {
					points,
					firstBand,
					bands: packedBands,
					west: west - roundingGuard,
					east: east + roundingGuard,
					roundingGuard,
				};
			});
			Object.freeze(polygon);
			return rings;
		});
		Object.freeze(source);
		return indexed;
	};
	const boundary = polygons(geography.boundary);
	const lakes = polygons(geography.lakes);
	indexes.set(geography, {
		boundary,
		lakes,
		rings: [...boundary.flat(), ...lakes.flat()],
		sourceBoundary: geography.boundary,
		sourceLakes: geography.lakes,
	});
}

function geographyIndex(geography: Geography) {
	const index = indexes.get(geography);
	return index?.sourceBoundary === geography.boundary &&
		index.sourceLakes === geography.lakes
		? index
		: undefined;
}

function containsIndexedRing([x, y]: number[], ring: IndexedRing) {
	if (x < ring.west || x > ring.east) return false;
	let inside = false;
	for (const i of ring.bands[band(y) - ring.firstBand] ?? []) {
		const [xi, yi] = ring.points[i];
		const [xj, yj] = ring.points[i ? i - 1 : ring.points.length - 1];
		if (Math.max(xi, xj) + ring.roundingGuard < x) break;
		if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)
			inside = !inside;
	}
	return inside;
}

function containsIndexedPolygon(point: number[], polygon: IndexedPolygon) {
	return (
		containsIndexedRing(point, polygon[0]) &&
		!polygon.slice(1).some((ring) => containsIndexedRing(point, ring))
	);
}

function* crossingEdges(geography: Geography, a: number[], b: number[]) {
	const index = geographyIndex(geography);
	if (!index) {
		for (const polygon of [...geography.boundary, ...geography.lakes])
			for (const ring of polygon)
				for (let i = 1; i < ring.length; i++) yield [ring[i - 1], ring[i]];
		return;
	}
	const first = band(Math.min(a[1], b[1]));
	const last = band(Math.max(a[1], b[1]));
	const west = Math.min(a[0], b[0]);
	const east = Math.max(a[0], b[0]);
	for (const ring of index.rings) {
		const { points, firstBand, bands } = ring;
		if (east < ring.west || west > ring.east) continue;
		for (
			let y = Math.max(first, firstBand);
			y <= Math.min(last, firstBand + bands.length - 1);
			y++
		)
			for (const i of bands[y - firstBand]) {
				if (!i) continue; // The original crossing scan excludes the implicit closing edge.
				const c = points[i - 1],
					d = points[i];
				if (Math.max(c[0], d[0]) + ring.roundingGuard < west) break;
				// An edge spanning several bands is tested exactly once.
				if (y === first || y === band(Math.min(c[1], d[1]))) yield [c, d];
			}
	}
}

// Partition at every polygon crossing: sampling alone can skip narrow channels.
// A tolerated water prefix applies only at an input point, never inside a link.
export function landConnection(
	geography: Geography,
	a: number[],
	b: number[],
	maxWaterPrefix = 0,
) {
	const index = geographyIndex(geography);
	const onLand = (point: number[]) =>
		index
			? index.boundary.some((polygon) =>
					containsIndexedPolygon(point, polygon),
				) &&
				!index.lakes.some((polygon) => containsIndexedPolygon(point, polygon))
			: geography.boundary.some((polygon) =>
					containsPolygon([point[0], point[1]], polygon),
				) &&
				!geography.lakes.some((polygon) =>
					containsPolygon([point[0], point[1]], polygon),
				);
	if (!onLand(b)) return false;
	if (index) {
		let hasSource = false;
		const shared = index.boundary.some((polygon) => {
			if (!containsIndexedPolygon(a, polygon)) return false;
			hasSource = true;
			return containsIndexedPolygon(b, polygon);
		});
		if (hasSource && !shared) return false;
	} else {
		const source = geography.boundary.filter((polygon) =>
			containsPolygon([a[0], a[1]], polygon),
		);
		if (
			source.length &&
			!source.some((polygon) => containsPolygon([b[0], b[1]], polygon))
		)
			return false;
	}
	const dx = b[0] - a[0],
		dy = b[1] - a[1];
	if (!dx && !dy) return true;
	const cuts = [0, 1];
	for (const [c, d] of crossingEdges(geography, a, b)) {
		if (
			Math.max(c[0], d[0]) < Math.min(a[0], b[0]) ||
			Math.min(c[0], d[0]) > Math.max(a[0], b[0]) ||
			Math.max(c[1], d[1]) < Math.min(a[1], b[1]) ||
			Math.min(c[1], d[1]) > Math.max(a[1], b[1])
		)
			continue;
		const ex = d[0] - c[0],
			ey = d[1] - c[1];
		const denominator = dx * ey - dy * ex;
		if (Math.abs(denominator) < 1e-15) continue;
		const cx = c[0] - a[0],
			cy = c[1] - a[1];
		const t = (cx * ey - cy * ex) / denominator;
		const u = (cx * dy - cy * dx) / denominator;
		if (t >= 0 && t <= 1 && u >= 0 && u <= 1) cuts.push(t);
	}
	cuts.sort((x, y) => x - y);
	let reachedLand = false;
	for (let i = 1; i < cuts.length; i++) {
		const start = cuts[i - 1],
			end = cuts[i];
		if (end - start < 1e-10) continue;
		if (
			onLand([a[0] + (dx * (start + end)) / 2, a[1] + (dy * (start + end)) / 2])
		)
			reachedLand = true;
		else if (reachedLand || end > maxWaterPrefix + 1e-10) return false;
	}
	return reachedLand;
}
