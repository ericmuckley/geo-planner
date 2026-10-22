type Position = [number, number];
type Polygon = Position[][];

export function containsRing([x, y]: Position, ring: number[][]) {
	let inside = false;
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const [xi, yi] = ring[i];
		const [xj, yj] = ring[j];
		if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)
			inside = !inside;
	}
	return inside;
}

export function containsPolygon(point: Position, polygon: number[][][]) {
	return (
		containsRing(point, polygon[0]) &&
		!polygon.slice(1).some((ring) => containsRing(point, ring))
	);
}

function signedArea(ring: Position[]) {
	let area = 0;
	for (let i = 1; i < ring.length; i++)
		area += ring[i - 1][0] * ring[i][1] - ring[i][0] * ring[i - 1][1];
	return area / 2;
}

// Trace the union of selected cells, preserving coastline gaps and lake holes.
// Interior lies on the left; left turns keep diagonally touching cells separate.
export function cellContours(
	mask: Uint8Array,
	width: number,
	height: number,
	west: number,
	south: number,
	step: number,
): Polygon[] {
	const stride = width + 1;
	const edges = new Uint8Array(stride * (height + 1));
	for (let y = 0; y < height; y++) {
		for (let x = 0; x < width; x++) {
			const cell = y * width + x;
			if (!mask[cell]) continue;
			if (y === 0 || !mask[cell - width]) edges[y * stride + x] |= 1;
			if (x === width - 1 || !mask[cell + 1]) edges[y * stride + x + 1] |= 2;
			if (y === height - 1 || !mask[cell + width])
				edges[(y + 1) * stride + x + 1] |= 4;
			if (x === 0 || !mask[cell - 1]) edges[(y + 1) * stride + x] |= 8;
		}
	}
	const rings: Position[][] = [];
	const moves = [1, stride, -1, -stride];
	for (let start = 0; start < edges.length; start++) {
		while (edges[start]) {
			let vertex = start;
			let direction = Math.floor(Math.log2(edges[start] & -edges[start]));
			const ring: Position[] = [];
			do {
				ring.push([
					Math.round((west + (vertex % stride) * step) * 1e6) / 1e6,
					Math.round((south + Math.floor(vertex / stride) * step) * 1e6) / 1e6,
				]);
				edges[vertex] &= ~(1 << direction);
				vertex += moves[direction];
				if (vertex === start) break;
				const next = [1, 0, 3, 2]
					.map((turn) => (direction + turn) % 4)
					.find((candidate) => edges[vertex] & (1 << candidate));
				if (next === undefined) throw new Error("Open cell contour");
				direction = next;
			} while (vertex !== start);
			ring.push(ring[0]);
			// Remove collinear cell corners without changing the cell union.
			const simplified = ring.filter((point, i) => {
				if (i === 0 || i === ring.length - 1) return true;
				const previous = ring[i - 1];
				const next = ring[i + 1];
				return !(
					(previous[0] === point[0] && next[0] === point[0]) ||
					(previous[1] === point[1] && next[1] === point[1])
				);
			});
			rings.push(simplified);
		}
	}
	const polygons = rings
		.filter((ring) => signedArea(ring) > 0)
		.map((ring) => [ring]);
	for (const hole of rings.filter((ring) => signedArea(ring) < 0)) {
		const parent = polygons
			.filter((polygon) => containsRing(hole[0], polygon[0]))
			.sort((a, b) => signedArea(a[0]) - signedArea(b[0]))[0];
		if (!parent) throw new Error("Cell contour hole has no exterior");
		parent.push(hole);
	}
	return polygons;
}
