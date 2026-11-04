/** Packed graph indices; costs, coordinates and native OSM IDs use their own types. */
export const MAX_UINT24 = 0xffffff;
const MAX_ENTRIES = MAX_UINT24 + 1;

function requireIndex(value: number, limit: number): void {
	if (!Number.isInteger(value) || value < 0 || value >= limit) {
		throw new RangeError("Packed graph index is outside its declared range");
	}
}

export function packUint24(values: ArrayLike<number>): Uint8Array {
	if (
		!Number.isInteger(values.length) ||
		values.length < 0 ||
		values.length > MAX_ENTRIES
	) {
		throw new RangeError("Packed graph array exceeds its entry limit");
	}
	const bytes = new Uint8Array(values.length * 3);
	for (let i = 0; i < values.length; i++) {
		const value = values[i];
		requireIndex(value, MAX_ENTRIES);
		bytes[3 * i] = value;
		bytes[3 * i + 1] = value >>> 8;
		bytes[3 * i + 2] = value >>> 16;
	}
	return bytes;
}

/** A view of packed bytes. It retains no expanded array or per-index objects. */
export class Uint24View {
	readonly length: number;
	readonly byteLength: number;
	readonly #bytes: Uint8Array;

	constructor(bytes: Uint8Array) {
		if (bytes.byteLength % 3 || bytes.byteLength / 3 > MAX_ENTRIES) {
			throw new RangeError("Invalid packed graph byte length");
		}
		this.#bytes = bytes;
		this.length = bytes.byteLength / 3;
		this.byteLength = bytes.byteLength;
	}

	at(index: number): number {
		requireIndex(index, this.length);
		const offset = index * 3;
		return (
			this.#bytes[offset] |
			(this.#bytes[offset + 1] << 8) |
			(this.#bytes[offset + 2] << 16)
		);
	}

	subarray(start: number, end: number = this.length): Uint24View {
		if (
			!Number.isInteger(start) ||
			!Number.isInteger(end) ||
			start < 0 ||
			end < start ||
			end > this.length
		) {
			throw new RangeError("Invalid packed graph subarray bounds");
		}
		return new Uint24View(this.#bytes.subarray(3 * start, 3 * end));
	}
}
