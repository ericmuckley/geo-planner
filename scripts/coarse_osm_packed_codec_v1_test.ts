import assert from "node:assert/strict";
import test from "node:test";
import {
	decodePackedWords,
	encodePackedWords,
	packedWordLayout,
} from "./coarse_osm_packed_codec_v1.ts";

test("independent golden modular delta, zigzag and byte-plane words", () => {
	// u16 values 1,3,2,65535 -> signed deltas 1,2,-1,-3 -> 2,4,1,5.
	const raw = Uint8Array.of(1, 0, 3, 0, 2, 0, 255, 255);
	const expected = Uint8Array.of(2, 4, 1, 5, 0, 0, 0, 0);
	assert.deepEqual(
		encodePackedWords(raw, { wordBytes: 2, lanes: 1 }),
		expected,
	);
	assert.deepEqual(
		decodePackedWords(expected, { wordBytes: 2, lanes: 1 }),
		raw,
	);
});

test("coordinate axes predict separately and preserve signed wrap", () => {
	const raw = new Uint8Array(16);
	const view = new DataView(raw.buffer);
	[2147483647, -2147483648, -2147483648, 2147483647].forEach((word, i) => {
		view.setInt32(i * 4, word, true);
	});
	const encoded = encodePackedWords(raw, { wordBytes: 4, lanes: 2 });
	assert.deepEqual(decodePackedWords(encoded, { wordBytes: 4, lanes: 2 }), raw);
	assert.deepEqual([...encoded.subarray(0, 4)], [254, 255, 2, 1]);
});

test("seeded unaligned words roundtrip all widths and lane layouts", () => {
	let seed = 20261102;
	for (const width of [1, 2, 3, 4] as const)
		for (const lanes of [1, 2] as const) {
			const allocation = new Uint8Array(20_000 * width + 2);
			const raw = allocation.subarray(1, allocation.length - 1);
			for (let i = 0; i < raw.length; i++) {
				seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
				raw[i] = seed >>> 24;
			}
			const layout = { wordBytes: width, lanes };
			const encoded = encodePackedWords(raw, layout);
			assert.deepEqual(decodePackedWords(encoded, layout), raw);
			assert.notEqual(encoded.buffer, raw.buffer);
		}
});

test("empty fields and declared file layouts, malformed shapes refused", () => {
	assert.deepEqual(packedWordLayout("routing/xy.i32"), {
		wordBytes: 4,
		lanes: 2,
	});
	assert.deepEqual(packedWordLayout("routing/targets.u24"), {
		wordBytes: 3,
		lanes: 1,
	});
	assert.equal(
		decodePackedWords(new Uint8Array(), { wordBytes: 3, lanes: 1 }).length,
		0,
	);
	assert.throws(() => packedWordLayout("routing/unknown.bin"));
	assert.throws(() =>
		decodePackedWords(Uint8Array.of(0), { wordBytes: 3, lanes: 1 }),
	);
	assert.throws(() =>
		encodePackedWords(new Uint8Array(4), { wordBytes: 4, lanes: 2 }),
	);
});
