import { containsPolygon } from "./coarse-contours";

type Geography = { boundary: number[][][][]; lakes: number[][][][] };

// Partition at every polygon crossing: sampling alone can skip narrow channels.
// A tolerated water prefix applies only at an input point, never inside a link.
export function landConnection(
	geography: Geography,
	a: number[],
	b: number[],
	maxWaterPrefix = 0,
) {
	const onLand = (point: number[]) =>
		geography.boundary.some((polygon) =>
			containsPolygon([point[0], point[1]], polygon),
		) &&
		!geography.lakes.some((polygon) =>
			containsPolygon([point[0], point[1]], polygon),
		);
	if (!onLand(b)) return false;
	const sourcePolygons = geography.boundary.filter((polygon) =>
		containsPolygon([a[0], a[1]], polygon),
	);
	if (
		sourcePolygons.length &&
		!sourcePolygons.some((polygon) => containsPolygon([b[0], b[1]], polygon))
	)
		return false;
	const dx = b[0] - a[0],
		dy = b[1] - a[1];
	if (!dx && !dy) return true;
	const cuts = [0, 1];
	for (const polygon of [...geography.boundary, ...geography.lakes])
		for (const ring of polygon)
			for (let i = 1; i < ring.length; i++) {
				const c = ring[i - 1],
					d = ring[i];
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
