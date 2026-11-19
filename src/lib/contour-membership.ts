import { containsPolygon, containsRing } from "../server/coarse-contours";
import type { Origin, ReachabilityResult } from "./reachability";

type Contours = ReachabilityResult["contours"];

export function contourPolygons(contours: Contours) {
	return contours.features.flatMap(({ geometry }) => {
		if (geometry.type === "Polygon") return [geometry.coordinates];
		if (geometry.type === "MultiPolygon") return geometry.coordinates;
		return [];
	});
}

export function isInEstimatedArea(
	{ lon, lat }: Origin,
	contours: Contours,
): boolean {
	return contourPolygons(contours).some((polygon) =>
		containsPolygon([lon, lat], polygon),
	);
}

function prepareRing(ring: number[][]) {
	let west = Infinity;
	let south = Infinity;
	let east = -Infinity;
	let north = -Infinity;
	for (const [lon, lat] of ring) {
		west = Math.min(west, lon);
		south = Math.min(south, lat);
		east = Math.max(east, lon);
		north = Math.max(north, lat);
	}
	const inBounds = (lon: number, lat: number) =>
		lon >= west && lon <= east && lat >= south && lat <= north;
	const direct = (lon: number, lat: number) =>
		inBounds(lon, lat) && containsRing([lon, lat], ring);
	if (ring.length < 64 || south === north) return direct;

	// A horizontal test ray can only cross edges in its latitude band.
	// Keep the original crossing rule and cap expanded storage for tall edges.
	const bands = Math.min(256, Math.ceil(ring.length / 8));
	const band = (lat: number) =>
		Math.min(bands - 1, Math.floor(((lat - south) / (north - south)) * bands));
	const edges: number[][] = Array.from({ length: bands }, () => []);
	let references = 0;
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const y1 = ring[i][1],
			y2 = ring[j][1];
		if (y1 === y2) continue;
		for (let k = band(Math.min(y1, y2)); k <= band(Math.max(y1, y2)); k++) {
			if (++references > ring.length * 8) return direct;
			edges[k].push(i);
		}
	}

	return (lon: number, lat: number) => {
		if (!inBounds(lon, lat)) return false;
		let inside = false;
		for (const i of edges[band(lat)]) {
			const [xi, yi] = ring[i];
			const [xj, yj] = ring[i === 0 ? ring.length - 1 : i - 1];
			if (
				yi > lat !== yj > lat &&
				lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi
			)
				inside = !inside;
		}
		return inside;
	};
}

export function areaMembership(contours: Contours) {
	const areas = contourPolygons(contours).map(([outer, ...holes]) => ({
		outer: prepareRing(outer),
		holes: holes.map(prepareRing),
	}));
	return (lon: number, lat: number) =>
		areas.some(
			({ outer, holes }) =>
				outer(lon, lat) && !holes.some((hole) => hole(lon, lat)),
		);
}
