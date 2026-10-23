import { gunzipSync } from "node:zlib";
import { landConnection, prepareGeography } from "./coarse-geography";
import {
	distanceKm,
	type GridData,
	gridPosition,
	type RoadVisit,
	type RoadVisits,
} from "./coarse-grid";

type VisitRow = {
	cell: number;
	speedKph: number;
	anchorIndex: number;
	offsets: number[][];
};

type EncodedVisits =
	| VisitRow[]
	| {
			encoding: string;
			cells: string;
			speeds: string;
			anchors: string;
			starts: string;
			offsets: string;
	  };

function gridBytes(value: string) {
	return value.startsWith("gzip:")
		? gunzipSync(Buffer.from(value.slice(5), "base64"), {
				maxOutputLength: 256_000_000,
			})
		: Buffer.from(value, "base64");
}

const littleEndian = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;
function gridWords(value: string, count: number): Uint16Array;
function gridWords(value: string, count: number, signed: true): Int16Array;
function gridWords(
	value: string,
	count: number,
	signed = false,
): Uint16Array | Int16Array {
	const raw = gridBytes(value);
	if (raw.length !== count * 2)
		throw new Error("Invalid grid word array length");
	const Words = signed ? Int16Array : Uint16Array;
	if (littleEndian && raw.byteOffset % 2 === 0)
		return new Words(raw.buffer, raw.byteOffset, count);
	const result = new Words(count);
	const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
	for (let i = 0; i < count; i++)
		result[i] = signed
			? view.getInt16(i * 2, true)
			: view.getUint16(i * 2, true);
	return result;
}

function packedVisits(
	data: Exclude<EncodedVisits, VisitRow[]>,
	grid: GridData,
	supplemental: boolean,
): RoadVisits {
	const cells = gridBytes(data.cells);
	const speeds = gridBytes(data.speeds);
	const anchors = gridBytes(data.anchors);
	const starts = gridBytes(data.starts);
	const offsets = gridBytes(data.offsets);
	const count = speeds.length;
	if (
		data.encoding !== "cell-visits-le-v1" ||
		cells.length !== count * 4 ||
		anchors.length !== count * 4 ||
		starts.length !== (count + 1) * 4 ||
		offsets.length % 4 !== 0 ||
		starts.readUInt32LE(0) !== 0 ||
		starts.readUInt32LE(count * 4) !== offsets.length / 4
	)
		throw new Error("Invalid packed road visits");
	const index = new Uint32Array(grid.width * grid.height);
	const read = (i: number) => {
		const start = starts.readUInt32LE(i * 4);
		const end = starts.readUInt32LE((i + 1) * 4);
		if (end < start + 2 || end > offsets.length / 4)
			throw new Error("Invalid packed road visit range");
		return decodeVisit(
			grid,
			{
				cell: cells.readUInt32LE(i * 4),
				speedKph: speeds[i],
				anchorIndex: anchors.readUInt32LE(i * 4),
				offsets: Array.from({ length: end - start }, (_, j) => [
					offsets.readInt16LE((start + j) * 4),
					offsets.readInt16LE((start + j) * 4 + 2),
				]),
			},
			supplemental,
		);
	};
	for (let i = 0; i < count; i++) {
		const cell = cells.readUInt32LE(i * 4);
		if (cell >= index.length || index[cell])
			throw new Error("Invalid bundled road visit cell");
		// Validate every visit now, retaining only the packed buffers/index. Reads
		// later materialize one visit with no cache that could grow across queries.
		read(i);
		index[cell] = i + 1;
	}
	return {
		size: count,
		get(cell) {
			return index[cell] ? read(index[cell] - 1) : undefined;
		},
		*[Symbol.iterator]() {
			for (let i = 0; i < count; i++)
				yield [cells.readUInt32LE(i * 4), read(i)];
		},
	};
}

function decodeVisit(
	grid: GridData,
	{ cell, speedKph, anchorIndex, offsets }: VisitRow,
	supplemental: boolean,
): RoadVisit {
	if (
		!Number.isInteger(cell) ||
		cell < 0 ||
		cell >= grid.width * grid.height ||
		!grid.traversable[cell] ||
		!Number.isFinite(speedKph) ||
		speedKph < grid.localSpeedKph ||
		speedKph > 105 ||
		!Number.isInteger(anchorIndex) ||
		anchorIndex < 0 ||
		anchorIndex >= offsets.length ||
		offsets.length < 2 ||
		offsets.some(
			(p) =>
				p.length !== 2 ||
				p.some(
					(v) => !Number.isInteger(v) || Math.abs(v) > grid.step * 50000 + 1,
				),
		)
	)
		throw new Error("Invalid bundled road visit");
	const center = [
		grid.bounds[0] + ((cell % grid.width) + 0.5) * grid.step,
		grid.bounds[1] + (Math.floor(cell / grid.width) + 0.5) * grid.step,
	];
	const points = offsets.map((p) => p.map((v, k) => center[k] + v / 100000));
	const anchor = gridPosition(grid, cell);
	const transferKm = distanceKm(points[anchorIndex], anchor);
	if (supplemental) {
		if (!landConnection(grid, points[anchorIndex], anchor))
			throw new Error("Road visit transfer crosses water or country boundary");
		if (
			grid.roadLayer &&
			(grid.roadLayer.transferDeciseconds[cell] !==
				Math.max(1, Math.ceil((transferKm / grid.localSpeedKph) * 36000)) ||
				distanceKm(
					points[anchorIndex],
					gridPosition(grid, grid.width * grid.height + cell),
				) > 1e-7)
		)
			throw new Error(
				"Road layer does not match its source visit or paid transfer",
			);
	} else if (transferKm > 1e-7)
		throw new Error("Road visit does not own its anchor");
	const cumulativeKm = [0];
	for (let i = 1; i < points.length; i++) {
		const km = distanceKm(points[i - 1], points[i]);
		if (!km) throw new Error("Duplicate road visit points");
		cumulativeKm.push(cumulativeKm[i - 1] + km);
	}
	return {
		speedKph,
		anchorIndex,
		points,
		cumulativeKm,
		...(supplemental ? { transferKm } : {}),
	};
}

type EncodedGrid = Omit<
	GridData,
	| "land"
	| "traversable"
	| "links"
	| "roadDeciseconds"
	| "displayLand"
	| "anchorOffsets"
	| "shoreLinks"
	| "roadVisits"
	| "supplementalRoadVisits"
	| "roadLayer"
> & {
	land: string;
	traversable: string;
	links: string;
	roadDeciseconds?: string;
	displayLand?: string;
	anchorOffsets?: string;
	shoreLinks?: string;
	roadVisits?: EncodedVisits;
	supplementalRoadVisits?: EncodedVisits;
	roadLayer?: {
		encoding: string;
		anchorOffsets: string;
		roadDeciseconds: string;
		transferDeciseconds: string;
	};
};

export function decodeGrid(data: EncodedGrid): GridData {
	const bytes = (value: string) => new Uint8Array(gridBytes(value));
	const grid = {
		...data,
		land: bytes(data.land),
		traversable: bytes(data.traversable),
		links: bytes(data.links),
		displayLand: data.displayLand ? bytes(data.displayLand) : undefined,
		shoreLinks: data.shoreLinks ? bytes(data.shoreLinks) : undefined,
		roadDeciseconds: undefined as Uint16Array | undefined,
		anchorOffsets: undefined as Int16Array | undefined,
		roadVisits: undefined as RoadVisits | undefined,
		supplementalRoadVisits: undefined as RoadVisits | undefined,
		roadLayer: undefined as GridData["roadLayer"],
	};
	const size = data.width * data.height;
	if (
		grid.land.length !== size ||
		grid.traversable.length !== size ||
		grid.links.length !== size * 4 ||
		(grid.displayLand && grid.displayLand.length !== size) ||
		(grid.shoreLinks && grid.shoreLinks.length !== size)
	)
		throw new Error("Invalid bundled coarse-grid data");
	if (data.roadDeciseconds) {
		grid.roadDeciseconds = gridWords(data.roadDeciseconds, size * 4);
	}
	if (data.anchorOffsets) {
		grid.anchorOffsets = gridWords(data.anchorOffsets, size * 2, true);
	}
	const decodeVisits = (encoded: EncodedVisits, supplemental: boolean) => {
		if (!Array.isArray(encoded))
			return packedVisits(encoded, grid, supplemental);
		const visits = new Map<number, RoadVisit>();
		for (const row of encoded) {
			if (visits.has(row.cell))
				throw new Error("Invalid bundled road visit cell");
			visits.set(row.cell, decodeVisit(grid, row, supplemental));
		}
		return visits;
	};
	if (data.roadLayer) {
		if (data.roadLayer.encoding !== "census-road-layer-le-v1")
			throw new Error("Invalid road layer encoding");
		grid.roadLayer = {
			anchorOffsets: gridWords(data.roadLayer.anchorOffsets, size * 2, true),
			roadDeciseconds: gridWords(data.roadLayer.roadDeciseconds, size * 4),
			transferDeciseconds: gridWords(data.roadLayer.transferDeciseconds, size),
		};
	}
	prepareGeography(grid);
	if (data.roadVisits) grid.roadVisits = decodeVisits(data.roadVisits, false);
	if (data.supplementalRoadVisits)
		grid.supplementalRoadVisits = decodeVisits(
			data.supplementalRoadVisits,
			true,
		);
	if (grid.roadLayer) {
		const transfers = grid.roadLayer.transferDeciseconds;
		let states = 0;
		for (const transfer of transfers) if (transfer) states++;
		if (states !== grid.supplementalRoadVisits?.size)
			throw new Error("Road layer source visits differ");
		const roads = grid.roadLayer.roadDeciseconds;
		const directions = [
			[1, 0],
			[1, 1],
			[0, 1],
			[-1, 1],
		];
		for (let key = 0; key < roads.length; key++) {
			if (!roads[key]) continue;
			const cell = Math.floor(key / 4),
				[dx, dy] = directions[key % 4];
			const x = (cell % grid.width) + dx,
				y = Math.floor(cell / grid.width) + dy;
			if (
				x < 0 ||
				x >= grid.width ||
				y < 0 ||
				y >= grid.height ||
				!transfers[cell] ||
				!transfers[y * grid.width + x]
			)
				throw new Error("Road layer link has no source state");
		}
	}
	return grid;
}
