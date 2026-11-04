/** Spherical geometry in degrees, with stable short-segment differences. */
export type Coordinate = readonly [number, number];
export const EARTH_METERS = 6371008.8;
const RAD = Math.PI / 180;

function longitudeDelta(a: number, b: number): number {
	let delta = b - a;
	if (delta > 180) delta -= 360;
	if (delta < -180) delta += 360;
	return delta * RAD;
}

function angle(a: Coordinate, b: Coordinate): number {
	const dy = Math.sin(((b[1] - a[1]) * RAD) / 2);
	const dx = Math.sin(longitudeDelta(a[0], b[0]) / 2);
	return (
		2 *
		Math.asin(
			Math.min(
				1,
				Math.sqrt(
					dy * dy + Math.cos(a[1] * RAD) * Math.cos(b[1] * RAD) * dx * dx,
				),
			),
		)
	);
}

export function sphericalDistance(a: Coordinate, b: Coordinate): number {
	return EARTH_METERS * angle(a, b);
}

export function nearestOnSegment(
	p: Coordinate,
	a: Coordinate,
	b: Coordinate,
): { distance: number; fraction: number; coordinate: Coordinate } {
	const ab = angle(a, b);
	const endpoint = () => {
		const da = sphericalDistance(p, a);
		const db = sphericalDistance(p, b);
		return da <= db
			? { distance: da, fraction: 0, coordinate: a }
			: { distance: db, fraction: 1, coordinate: b };
	};
	if (ab < 1e-12 || ab > Math.PI - 1e-12) return endpoint();
	const lat = a[1] * RAD;
	const components = (q: Coordinate) => {
		const dl = longitudeDelta(a[0], q[0]);
		const east = Math.sin(dl) * Math.cos(q[1] * RAD);
		const north =
			Math.sin((q[1] - a[1]) * RAD) +
			2 * Math.sin(lat) * Math.cos(q[1] * RAD) * Math.sin(dl / 2) ** 2;
		const dy = Math.sin(((q[1] - a[1]) * RAD) / 2);
		return {
			east,
			north,
			origin:
				1 -
				2 *
					(dy * dy +
						Math.cos(lat) * Math.cos(q[1] * RAD) * Math.sin(dl / 2) ** 2),
		};
	};
	const head = components(b);
	const norm = Math.hypot(head.east, head.north);
	const eastHeading = head.east / norm;
	const northHeading = head.north / norm;
	const point = components(p);
	const alongDot = point.east * eastHeading + point.north * northHeading;
	// At the great-circle pole every point ties; floating residuals must not
	// select an arbitrary interior paid position.
	if (Math.hypot(alongDot, point.origin) < 1e-14) return endpoint();
	const along = Math.atan2(alongDot, point.origin);
	if (along <= 0 || along >= ab) return endpoint();
	const cross = point.east * northHeading - point.north * eastHeading;
	const distance = EARTH_METERS * Math.asin(Math.min(1, Math.abs(cross)));
	const lon = a[0] * RAD;
	const c = Math.cos(along);
	const s = Math.sin(along);
	const x =
		Math.cos(lat) * Math.cos(lon) * c +
		(-Math.sin(lon) * eastHeading -
			Math.sin(lat) * Math.cos(lon) * northHeading) *
			s;
	const y =
		Math.cos(lat) * Math.sin(lon) * c +
		(Math.cos(lon) * eastHeading -
			Math.sin(lat) * Math.sin(lon) * northHeading) *
			s;
	const z = Math.sin(lat) * c + Math.cos(lat) * northHeading * s;
	return {
		distance,
		fraction: along / ab,
		coordinate: [Math.atan2(y, x) / RAD, Math.atan2(z, Math.hypot(x, y)) / RAD],
	};
}

/** Cell keys hold the top twelve bits of offset E7 x/y, interleaved. */
export function cellDistanceLowerMeters(p: Coordinate, key: number): number {
	let x = 0;
	let y = 0;
	for (let bit = 0; bit < 12; bit++) {
		x |= ((key >>> (2 * bit)) & 1) << bit;
		y |= ((key >>> (2 * bit + 1)) & 1) << bit;
	}
	const west = Math.max(-180, (x * 1048576 - 1800000000) / 1e7);
	const east = Math.min(180, ((x + 1) * 1048576 - 1 - 1800000000) / 1e7);
	const south = Math.max(-90, (y * 1048576 - 900000000) / 1e7);
	const north = Math.min(90, ((y + 1) * 1048576 - 1 - 900000000) / 1e7);
	if (west > east || south > north)
		throw new Error("Cell outside coordinate domain");
	let longitude = p[0];
	if (longitude < west || longitude > east)
		longitude =
			Math.abs(longitudeDelta(p[0], west)) <=
			Math.abs(longitudeDelta(p[0], east))
				? west
				: east;
	const delta = longitudeDelta(p[0], longitude);
	const optimum =
		Math.atan2(Math.sin(p[1] * RAD), Math.cos(p[1] * RAD) * Math.cos(delta)) /
		RAD;
	let distance = Math.min(
		sphericalDistance(p, [longitude, south]),
		sphericalDistance(p, [longitude, north]),
	);
	if (optimum >= south && optimum <= north)
		distance = Math.min(distance, sphericalDistance(p, [longitude, optimum]));
	return Math.max(0, distance - 1);
}
