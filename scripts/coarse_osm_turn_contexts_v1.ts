/** Read-only history states for source-audited static single-via-way no-turns. */
import { MAX_UINT24, Uint24View } from "./coarse_osm_u24_v1.ts";

export const TURN_CONTEXT_FILES = [
	"context/state-offsets.u32",
	"context/state-arcs.u24",
	"context/exit-offsets.u32",
	"context/exit-arcs.u24",
	"context/triggers.u24",
	"context/trigger-incoming.bit",
] as const;
export type TurnContextFiles = Record<
	(typeof TURN_CONTEXT_FILES)[number],
	Uint8Array
>;

function integer(value: number, maximum: number) {
	if (!Number.isInteger(value) || value < 0 || value > maximum)
		throw new RangeError("Turn-context integer domain");
}
function find(view: Uint24View, start: number, end: number, value: number) {
	const limit = end;
	while (start < end) {
		const middle = Math.floor((start + end) / 2);
		if (view.at(middle) < value) start = middle + 1;
		else end = middle;
	}
	return start < limit && view.at(start) === value ? start : -1;
}

export class TurnContexts {
	readonly arcs: number;
	readonly groups: number;
	readonly states: number;
	readonly backingBytes: number;
	readonly #stateOffsets: Uint32Array;
	readonly #stateArcs: Uint24View;
	readonly #exitOffsets: Uint32Array;
	readonly #exitArcs: Uint24View;
	readonly #triggers: Uint24View;
	readonly #incoming: Uint8Array;

	constructor(arcs: number, files: TurnContextFiles) {
		integer(arcs, MAX_UINT24);
		if (!arcs) throw new RangeError("Turn-context empty graph");
		if (
			Object.keys(files).sort().join() !== [...TURN_CONTEXT_FILES].sort().join()
		)
			throw new RangeError("Turn-context field set");
		const buffers = new Set<ArrayBuffer>();
		for (const name of TURN_CONTEXT_FILES) {
			const bytes = files[name];
			if (
				!(bytes instanceof Uint8Array) ||
				!(bytes.buffer instanceof ArrayBuffer) ||
				bytes.byteOffset !== 0 ||
				bytes.byteLength !== bytes.buffer.byteLength
			)
				throw new RangeError("Turn-context fields require owned buffers");
			buffers.add(bytes.buffer);
		}
		this.backingBytes = [...buffers].reduce((sum, b) => sum + b.byteLength, 0);
		if (this.backingBytes > 16 * 1024 ** 2)
			throw new RangeError("Turn-context data backing limit");
		const words = (
			name: "context/state-offsets.u32" | "context/exit-offsets.u32",
		) => {
			const bytes = files[name];
			if (bytes.byteLength % 4) throw new RangeError("Turn-context u32 length");
			return new Uint32Array(bytes.buffer);
		};
		this.arcs = arcs;
		this.#stateOffsets = words("context/state-offsets.u32");
		this.#exitOffsets = words("context/exit-offsets.u32");
		this.#stateArcs = new Uint24View(files["context/state-arcs.u24"]);
		this.#exitArcs = new Uint24View(files["context/exit-arcs.u24"]);
		this.#triggers = new Uint24View(files["context/triggers.u24"]);
		this.#incoming = files["context/trigger-incoming.bit"];
		this.groups = this.#stateOffsets.length - 1;
		this.states = this.#stateArcs.length;
		integer(this.groups, 100000);
		integer(this.states, 1000000);
		if (
			this.#exitOffsets.length !== this.groups + 1 ||
			this.#triggers.length % 3 ||
			this.#incoming.length !== Math.ceil(arcs / 8)
		)
			throw new RangeError("Turn-context column dimensions");
		for (const [offsets, values] of [
			[this.#stateOffsets, this.#stateArcs],
			[this.#exitOffsets, this.#exitArcs],
		] as const) {
			if (offsets[0] !== 0 || offsets[this.groups] !== values.length)
				throw new RangeError("Turn-context offsets");
			for (let group = 0; group < this.groups; group++) {
				if (offsets[group] > offsets[group + 1])
					throw new RangeError("Turn-context offset order");
				let previous = -1;
				for (let i = offsets[group]; i < offsets[group + 1]; i++) {
					const arc = values.at(i);
					if (arc >= arcs || arc <= previous)
						throw new RangeError("Turn-context arc range/order");
					previous = arc;
				}
			}
		}
		for (let group = 0; group < this.groups; group++)
			for (
				let i = this.#exitOffsets[group];
				i < this.#exitOffsets[group + 1];
				i++
			)
				if (
					find(
						this.#stateArcs,
						this.#stateOffsets[group],
						this.#stateOffsets[group + 1],
						this.#exitArcs.at(i),
					) >= 0
				)
					throw new RangeError("Turn-context via/exit overlap");
		const expected = new Uint8Array(this.#incoming.length);
		let previousIn = -1,
			previousOut = -1;
		for (let i = 0; i < this.#triggers.length; i += 3) {
			const before = this.#triggers.at(i),
				after = this.#triggers.at(i + 1),
				state = this.#triggers.at(i + 2);
			if (
				before >= arcs ||
				after >= arcs ||
				before === after ||
				state >= this.states ||
				this.#stateArcs.at(state) !== after ||
				before < previousIn ||
				(before === previousIn && after <= previousOut)
			)
				throw new RangeError("Turn-context trigger identity/order");
			expected[before >> 3] |= 1 << (before & 7);
			previousIn = before;
			previousOut = after;
		}
		for (let i = 0; i < expected.length; i++)
			if (expected[i] !== this.#incoming[i])
				throw new RangeError("Turn-context incoming bitset");
	}

	physicalArc(state: number): number {
		integer(state, this.arcs + this.states - 1);
		return state < this.arcs ? state : this.#stateArcs.at(state - this.arcs);
	}

	/** Caller separately enforces physical adjacency, source turns and node rules. */
	nextState(state: number, following: number): number | null {
		integer(state, this.arcs + this.states - 1);
		integer(following, this.arcs - 1);
		let before = state;
		if (state >= this.arcs) {
			const index = state - this.arcs;
			before = this.#stateArcs.at(index);
			let low = 0,
				high = this.#stateOffsets.length;
			while (low < high) {
				const middle = Math.floor((low + high) / 2);
				if (this.#stateOffsets[middle] <= index) low = middle + 1;
				else high = middle;
			}
			const group = low - 1;
			const sameWay = find(
				this.#stateArcs,
				this.#stateOffsets[group],
				this.#stateOffsets[group + 1],
				following,
			);
			if (sameWay >= 0) return this.arcs + sameWay;
			if (
				find(
					this.#exitArcs,
					this.#exitOffsets[group],
					this.#exitOffsets[group + 1],
					following,
				) >= 0
			)
				return null;
		}
		if (!(this.#incoming[before >> 3] & (1 << (before & 7)))) return following;
		let low = 0,
			high = this.#triggers.length / 3;
		while (low < high) {
			const middle = Math.floor((low + high) / 2),
				incoming = this.#triggers.at(3 * middle),
				outgoing = this.#triggers.at(3 * middle + 1);
			if (incoming < before || (incoming === before && outgoing < following))
				low = middle + 1;
			else high = middle;
		}
		if (
			low < this.#triggers.length / 3 &&
			this.#triggers.at(3 * low) === before &&
			this.#triggers.at(3 * low + 1) === following
		)
			return this.arcs + this.#triggers.at(3 * low + 2);
		return following;
	}
}
