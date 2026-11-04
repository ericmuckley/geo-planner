/** Reversible integer prediction and byte planes before ordinary gzip. */
export type PackedWordLayout = { wordBytes: 1 | 2 | 3 | 4; lanes: 1 | 2 };

export function packedWordLayout(name: string): PackedWordLayout {
	if (name.endsWith("/xy.i32")) return { wordBytes: 4, lanes: 2 };
	if (name.endsWith(".u24")) return { wordBytes: 3, lanes: 1 };
	if (name.endsWith(".u32")) return { wordBytes: 4, lanes: 1 };
	if (name.endsWith(".u16")) return { wordBytes: 2, lanes: 1 };
	if (name.endsWith(".u8")) return { wordBytes: 1, lanes: 1 };
	throw new Error("Unknown packed integer field");
}

function validate(bytes: Uint8Array, layout: PackedWordLayout): number {
	const { wordBytes, lanes } = layout;
	if (
		![1, 2, 3, 4].includes(wordBytes) ||
		![1, 2].includes(lanes) ||
		bytes.length > 67_108_864 ||
		bytes.length % (wordBytes * lanes)
	) {
		throw new Error("Invalid packed integer layout/length");
	}
	return bytes.length / wordBytes;
}

export function encodePackedWords(
	raw: Uint8Array,
	layout: PackedWordLayout,
): Uint8Array {
	const count = validate(raw, layout);
	const { wordBytes, lanes } = layout;
	if (wordBytes === 1) return Uint8Array.from(raw);
	const output = new Uint8Array(raw.length);
	const previous = new Uint32Array(lanes);
	const shift = 32 - 8 * wordBytes;
	for (let i = 0; i < count; i++) {
		let word = 0;
		for (let j = 0; j < wordBytes; j++)
			word |= raw[i * wordBytes + j] << (8 * j);
		const lane = i % lanes;
		// Signed modular differences preserve every bit even across integer wrap.
		const delta = ((word - previous[lane]) << shift) >> shift;
		previous[lane] = word;
		const zigzag = (delta << 1) ^ (delta >> (8 * wordBytes - 1));
		for (let j = 0; j < wordBytes; j++)
			output[j * count + i] = zigzag >>> (8 * j);
	}
	return output;
}

export function decodePackedWords(
	encoded: Uint8Array,
	layout: PackedWordLayout,
): Uint8Array {
	const count = validate(encoded, layout);
	const { wordBytes, lanes } = layout;
	if (wordBytes === 1) return Uint8Array.from(encoded);
	const output = new Uint8Array(encoded.length);
	const previous = new Uint32Array(lanes);
	const mask = wordBytes === 4 ? 0xffffffff : 2 ** (8 * wordBytes) - 1;
	for (let i = 0; i < count; i++) {
		let zigzag = 0;
		for (let j = 0; j < wordBytes; j++)
			zigzag |= encoded[j * count + i] << (8 * j);
		const delta = (zigzag >>> 1) ^ -(zigzag & 1);
		const lane = i % lanes;
		const word = (previous[lane] + delta) & mask;
		previous[lane] = word;
		for (let j = 0; j < wordBytes; j++)
			output[i * wordBytes + j] = word >>> (8 * j);
	}
	return output;
}
