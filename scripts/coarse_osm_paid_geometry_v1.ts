/** Compact source-paid shape reader. Input bytes are owned after validation. */
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { Uint24View } from "./coarse_osm_u24_v1.ts";

export const PAID_GEOMETRY_FILES = [
	"geometry/curve-keys.u24",
	"geometry/curve-offsets.u32",
	"geometry/curve-packets.u8",
	"geometry/long-keys.u24",
	"geometry/long-lengths.u16",
	"geometry/long-overflow-keys.u24",
	"geometry/long-overflow-units.u32",
] as const;

export type PaidGeometryFiles = Record<
	(typeof PAID_GEOMETRY_FILES)[number],
	Uint8Array
>;
export type PaidShapePoint = {
	xE7: number;
	yE7: number;
	/** Progress from canonical tail, in each direction's source travel time. */
	forward: number;
	backward: number;
};

function require(valid: unknown, message: string): asserts valid {
	if (!valid) throw new Error(message);
}

function view(bytes: Uint8Array, width: number): DataView {
	require(bytes.byteLength % width === 0, "Paid geometry word shape");
	return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
}

function lowerBound(keys: Uint24View, value: number): number {
	let lo = 0;
	let hi = keys.length;
	while (lo < hi) {
		const middle = (lo + hi) >>> 1;
		if (keys.at(middle) < value) lo = middle + 1;
		else hi = middle;
	}
	return lo;
}

export class PaidRoadGeometry {
	readonly retainedBackingBufferBytes: number;
	readonly curvedSpans: number;
	readonly longSpans: number;
	readonly #graph: PackedCarGraph;
	readonly #keys: Uint24View;
	readonly #offsets: DataView;
	readonly #packets: Uint8Array;
	readonly #longKeys: Uint24View;
	readonly #lengths: DataView;
	readonly #overflowKeys: Uint24View;
	readonly #overflowUnits: DataView;

	constructor(graph: PackedCarGraph, files: PaidGeometryFiles) {
		require(Object.keys(files).length === PAID_GEOMETRY_FILES.length &&
			PAID_GEOMETRY_FILES.every(
				(name) => files[name] instanceof Uint8Array,
			), "Paid geometry exact file roster");
		require(Object.values(files).reduce(
			(sum, bytes) => sum + bytes.byteLength,
			0,
		) <=
			48 * 1024 * 1024, "Paid geometry serialized cap");
		this.#graph = graph;
		this.#keys = new Uint24View(files["geometry/curve-keys.u24"]);
		this.#offsets = view(files["geometry/curve-offsets.u32"], 4);
		this.#packets = files["geometry/curve-packets.u8"];
		this.#longKeys = new Uint24View(files["geometry/long-keys.u24"]);
		this.#lengths = view(files["geometry/long-lengths.u16"], 2);
		this.#overflowKeys = new Uint24View(
			files["geometry/long-overflow-keys.u24"],
		);
		this.#overflowUnits = view(files["geometry/long-overflow-units.u32"], 4);
		this.curvedSpans = this.#keys.length;
		this.longSpans = this.#longKeys.length;
		require(this.#offsets.byteLength === 4 * (this.curvedSpans + 1) &&
			this.#offsets.getUint32(0, true) === 0 &&
			this.#offsets.getUint32(4 * this.curvedSpans, true) ===
				this.#packets.byteLength, "Paid curve offsets");
		require(this.#lengths.byteLength === 2 * this.longSpans &&
			this.#overflowUnits.byteLength ===
				4 * this.#overflowKeys.length, "Paid length index shape");
		for (const keys of [this.#keys, this.#longKeys, this.#overflowKeys]) {
			let previous = -1;
			for (let i = 0; i < keys.length; i++) {
				const key = keys.at(i);
				require(key > previous &&
					key < graph.arcs &&
					this.canonicalArc(key) === key, "Paid sorted physical arc keys");
				previous = key;
			}
		}
		let overflow = 0;
		for (let i = 0; i < this.longSpans; i++) {
			const units = this.#lengths.getUint16(2 * i, true);
			require(units >= 127, "Paid long-span length lower bound");
			if (units === 65535) {
				require(overflow < this.#overflowKeys.length &&
					this.#overflowKeys.at(overflow) === this.#longKeys.at(i) &&
					this.#overflowUnits.getUint32(4 * overflow, true) >=
						65535, "Paid length overflow correspondence");
				overflow++;
			}
		}
		require(overflow ===
			this.#overflowKeys.length, "Paid unused length overflow");
		for (let row = 0; row < this.curvedSpans; row++) {
			require(this.#offsets.getUint32(4 * row, true) <
				this.#offsets.getUint32(4 * (row + 1), true), "Paid nonempty packet");
			this.visitPoints(this.#keys.at(row), () => {});
		}
		const buffers = new Set(Object.values(files).map((bytes) => bytes.buffer));
		this.retainedBackingBufferBytes = [...buffers].reduce(
			(sum, buffer) => sum + buffer.byteLength,
			0,
		);
	}

	canonicalArc(arc: number): number {
		const reverse = this.#graph.reverseArc(arc);
		return reverse === null ? arc : Math.min(arc, reverse);
	}

	longArc(row: number): number {
		return this.#longKeys.at(row);
	}

	/** Upward bound on the full source length; short spans have a 1000 m bound. */
	lengthUpperMeters(arc: number): number {
		const key = this.canonicalArc(arc);
		const row = lowerBound(this.#longKeys, key);
		if (row === this.longSpans || this.#longKeys.at(row) !== key) return 1000;
		let units = this.#lengths.getUint16(2 * row, true);
		if (units === 65535)
			units = this.#overflowUnits.getUint32(
				4 * lowerBound(this.#overflowKeys, key),
				true,
			);
		return units * 8;
	}

	/** Always visits canonical direction, including both implicit endpoints. */
	visitPoints(arc: number, visit: (point: PaidShapePoint) => void): void {
		const key = this.canonicalArc(arc);
		const reverse = this.#graph.reverseArc(key);
		const tail = this.#graph.coordinate(this.#graph.arcTail(key));
		let x = Math.round(tail[0] * 1e7);
		let y = Math.round(tail[1] * 1e7);
		let forward = 0;
		let backward = 0;
		visit({ xE7: x, yE7: y, forward, backward });
		const row = lowerBound(this.#keys, key);
		if (row < this.curvedSpans && this.#keys.at(row) === key) {
			let cursor = this.#offsets.getUint32(4 * row, true);
			const end = this.#offsets.getUint32(4 * (row + 1), true);
			let points = 0;
			const word = (): number => {
				let value = 0;
				for (let i = 0; i < 5; i++) {
					require(cursor < end, "Paid truncated varint");
					const byte = this.#packets[cursor++];
					value += (byte & 127) * 2 ** (7 * i);
					if (byte < 128) {
						require(value <= 0xffffffff &&
							(i === 0 || byte !== 0), "Paid canonical uint32 varint");
						return value;
					}
				}
				throw new Error("Paid excessive varint");
			};
			while (cursor < end) {
				const dx = word();
				const dy = word();
				x = (x + ((dx >>> 1) ^ -(dx & 1))) | 0;
				y = (y + ((dy >>> 1) ^ -(dy & 1))) | 0;
				require(Math.abs(x) <= 1800000000 &&
					Math.abs(y) <= 900000000 &&
					cursor + 4 <= end &&
					++points <= 1048576, "Paid packet coordinate/length");
				const f = this.#packets[cursor] + 256 * this.#packets[cursor + 1];
				const b = this.#packets[cursor + 2] + 256 * this.#packets[cursor + 3];
				cursor += 4;
				require(f >= forward &&
					b >= backward &&
					(reverse !== null || b === 0), "Paid monotone directional prefix");
				forward = f;
				backward = b;
				visit({ xE7: x, yE7: y, forward, backward });
			}
			require(cursor === end, "Paid complete packet");
		}
		const head = this.#graph.coordinate(this.#graph.arcTarget(key));
		visit({
			xE7: Math.round(head[0] * 1e7),
			yE7: Math.round(head[1] * 1e7),
			forward: 65535,
			backward: reverse === null ? 0 : 65535,
		});
	}
}
