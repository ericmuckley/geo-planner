/** Offline candidate reader. Own the supplied bytes exclusively after validation. */
import { MAX_UINT24, Uint24View } from "./coarse_osm_u24_v1.ts";

export const PACKED_CAR_FILES = [
	"routing/xy.i32",
	"routing/offsets.u24",
	"routing/targets.u24",
	"routing/costs.u16",
	"routing/cost-overflow-arcs.u24",
	"routing/cost-overflow-ticks.u32",
	"routing/reverse.u8",
	"routing/reverse-overflow-arcs.u24",
	"routing/reverse-overflow-targets.u24",
	"routing/node-flags.u8",
	"routing/forbidden-turns.u24",
] as const;

export type PackedCarFiles = Record<
	(typeof PACKED_CAR_FILES)[number],
	Uint8Array
>;

function require(valid: unknown, message: string): asserts valid {
	if (!valid) throw new Error(message);
}

function dataView(bytes: Uint8Array, width: number): DataView {
	require(bytes.byteLength % width === 0, "Invalid packed word length");
	return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
}

export class PackedCarGraph {
	readonly vertices: number;
	readonly arcs: number;
	readonly retainedBackingBufferBytes: number;
	readonly #xy: DataView;
	readonly #offsets: Uint24View;
	readonly #targets: Uint24View;
	readonly #costs: DataView;
	readonly #costKeys: Uint24View;
	readonly #costValues: DataView;
	readonly #reverse: Uint8Array;
	readonly #reverseKeys: Uint24View;
	readonly #reverseValues: Uint24View;
	readonly #flags: Uint8Array;
	readonly #forbidden: Uint24View;
	readonly #hasForbidden: Uint8Array;

	constructor(files: PackedCarFiles) {
		require(Object.keys(files).length === PACKED_CAR_FILES.length &&
			PACKED_CAR_FILES.every(
				(name) => files[name] instanceof Uint8Array,
			), "Packed graph file roster");
		this.#xy = dataView(files["routing/xy.i32"], 4);
		this.#offsets = new Uint24View(files["routing/offsets.u24"]);
		this.#targets = new Uint24View(files["routing/targets.u24"]);
		this.#costs = dataView(files["routing/costs.u16"], 2);
		this.#costKeys = new Uint24View(files["routing/cost-overflow-arcs.u24"]);
		this.#costValues = dataView(files["routing/cost-overflow-ticks.u32"], 4);
		this.#reverse = files["routing/reverse.u8"];
		this.#reverseKeys = new Uint24View(
			files["routing/reverse-overflow-arcs.u24"],
		);
		this.#reverseValues = new Uint24View(
			files["routing/reverse-overflow-targets.u24"],
		);
		this.#flags = files["routing/node-flags.u8"];
		this.#forbidden = new Uint24View(files["routing/forbidden-turns.u24"]);
		this.vertices = this.#flags.length;
		this.arcs = this.#targets.length;
		require(this.vertices <= MAX_UINT24 &&
			this.arcs <= MAX_UINT24, "Packed graph index domain");
		require(this.#xy.byteLength === 8 * this.vertices &&
			this.#offsets.length === this.vertices + 1 &&
			this.#offsets.at(0) === 0 &&
			this.#offsets.at(this.vertices) ===
				this.arcs, "Packed graph vertex shape");
		require(this.#costs.byteLength === 2 * this.arcs &&
			this.#reverse.length === this.arcs &&
			this.#costKeys.length * 4 === this.#costValues.byteLength &&
			this.#reverseKeys.length === this.#reverseValues.length &&
			this.#forbidden.length % 2 === 0, "Packed graph arc/overflow/turn shape");
		this.#validateKeys(this.#costKeys);
		this.#validateKeys(this.#reverseKeys);
		for (let i = 0; i < this.#costKeys.length; i++) {
			require(this.#costs.getUint16(2 * this.#costKeys.at(i), true) === 65535 &&
				this.#costValues.getUint32(4 * i, true) >=
					65535, "Packed cost overflow sentinel");
		}
		for (let i = 0; i < this.#reverseKeys.length; i++) {
			require(this.#reverse[this.#reverseKeys.at(i)] === 254 &&
				this.#reverseValues.at(i) <
					this.arcs, "Packed reverse overflow sentinel");
		}
		for (let vertex = 0; vertex < this.vertices; vertex++) {
			const start = this.#offsets.at(vertex);
			const end = this.#offsets.at(vertex + 1);
			const x = this.#xy.getInt32(8 * vertex, true);
			const y = this.#xy.getInt32(8 * vertex + 4, true);
			require(start <= end &&
				end <= this.arcs &&
				this.#flags[vertex] < 8 &&
				Math.abs(x) <= 1800000000 &&
				Math.abs(y) <= 900000000, "Packed vertex coordinate/flag/CSR range");
			for (let arc = start; arc < end; arc++) {
				require(this.#targets.at(arc) < this.vertices, "Packed arc target");
				require(this.arcCostTicks(arc) > 0, "Packed positive physical cost");
				const reverse = this.reverseArc(arc);
				if (reverse !== null) {
					require(this.#targets.at(reverse) === vertex &&
						this.reverseArc(reverse) ===
							arc, "Packed physical reverse identity");
				}
			}
		}
		this.#hasForbidden = new Uint8Array(
			this.#forbidden.length ? Math.ceil(this.arcs / 8) : 0,
		);
		let previousIncoming = -1;
		let previousOutgoing = -1;
		for (let i = 0; i < this.#forbidden.length; i += 2) {
			const incoming = this.#forbidden.at(i);
			const outgoing = this.#forbidden.at(i + 1);
			require(incoming < this.arcs &&
				outgoing < this.arcs &&
				(incoming > previousIncoming ||
					(incoming === previousIncoming && outgoing > previousOutgoing)) &&
				this.#targets.at(incoming) ===
					this.arcTail(outgoing), "Packed sorted continuous forbidden turns");
			this.#hasForbidden[incoming >>> 3] |= 1 << (incoming & 7);
			previousIncoming = incoming;
			previousOutgoing = outgoing;
		}
		const buffers = new Set(Object.values(files).map((bytes) => bytes.buffer));
		buffers.add(this.#hasForbidden.buffer);
		this.retainedBackingBufferBytes = [...buffers].reduce(
			(sum, buffer) => sum + buffer.byteLength,
			0,
		);
	}

	#validateKeys(keys: Uint24View): void {
		let previous = -1;
		for (let i = 0; i < keys.length; i++) {
			const key = keys.at(i);
			require(key > previous && key < this.arcs, "Packed sorted overflow keys");
			previous = key;
		}
	}

	#arc(index: number): void {
		require(Number.isInteger(index) &&
			index >= 0 &&
			index < this.arcs, "Packed arc index range");
	}

	#vertex(index: number): void {
		require(Number.isInteger(index) &&
			index >= 0 &&
			index < this.vertices, "Packed vertex index range");
	}

	#overflow(keys: Uint24View, index: number): number {
		let lo = 0;
		let hi = keys.length;
		while (lo < hi) {
			const middle = (lo + hi) >>> 1;
			if (keys.at(middle) < index) lo = middle + 1;
			else hi = middle;
		}
		require(lo < keys.length &&
			keys.at(lo) === index, "Missing packed overflow");
		return lo;
	}

	coordinate(vertex: number): [number, number] {
		this.#vertex(vertex);
		return [
			this.#xy.getInt32(8 * vertex, true) / 1e7,
			this.#xy.getInt32(8 * vertex + 4, true) / 1e7,
		];
	}

	nodeFlags(vertex: number): number {
		this.#vertex(vertex);
		return this.#flags[vertex];
	}

	outgoingStart(vertex: number): number {
		this.#vertex(vertex);
		return this.#offsets.at(vertex);
	}

	outgoingEnd(vertex: number): number {
		this.#vertex(vertex);
		return this.#offsets.at(vertex + 1);
	}

	arcTarget(arc: number): number {
		this.#arc(arc);
		return this.#targets.at(arc);
	}

	arcTail(arc: number): number {
		this.#arc(arc);
		let lo = 0;
		let hi = this.vertices + 1;
		while (lo < hi) {
			const middle = (lo + hi) >>> 1;
			if (this.#offsets.at(middle) <= arc) lo = middle + 1;
			else hi = middle;
		}
		return lo - 1;
	}

	arcCostTicks(arc: number): number {
		this.#arc(arc);
		const word = this.#costs.getUint16(2 * arc, true);
		return word === 65535
			? this.#costValues.getUint32(
					4 * this.#overflow(this.#costKeys, arc),
					true,
				)
			: word;
	}

	reverseArc(arc: number): number | null {
		this.#arc(arc);
		const word = this.#reverse[arc];
		if (word === 255) return null;
		const head = this.#targets.at(arc);
		const start = this.#offsets.at(head);
		const end = this.#offsets.at(head + 1);
		const reverse =
			word === 254
				? this.#reverseValues.at(this.#overflow(this.#reverseKeys, arc))
				: start + word;
		require(reverse >= start && reverse < end, "Packed reverse row range");
		return reverse;
	}

	forbidsTurn(incoming: number, outgoing: number): boolean {
		this.#arc(incoming);
		this.#arc(outgoing);
		if (!(this.#hasForbidden[incoming >>> 3] & (1 << (incoming & 7)))) {
			return false;
		}
		let lo = 0;
		let hi = this.#forbidden.length / 2;
		while (lo < hi) {
			const middle = (lo + hi) >>> 1;
			const a = this.#forbidden.at(2 * middle);
			const b = this.#forbidden.at(2 * middle + 1);
			if (a < incoming || (a === incoming && b < outgoing)) lo = middle + 1;
			else hi = middle;
		}
		return (
			lo < this.#forbidden.length / 2 &&
			this.#forbidden.at(2 * lo) === incoming &&
			this.#forbidden.at(2 * lo + 1) === outgoing
		);
	}
}
