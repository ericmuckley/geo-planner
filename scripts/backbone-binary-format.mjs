import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";

export const magic = Buffer.from("GEOBBP01");
export const maxDescriptorBytes = 1_048_576;
export const sha256 = (bytes) =>
	createHash("sha256").update(bytes).digest("hex");
const typeSizes = { B: 1, I: 4, d: 8 };
const nativeLittleEndian = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

export function encodeContainer(kept, graphEntries, stats) {
	const entries = [];
	const payloads = [];
	let offset = 0;
	function add(name, kind, gzip, extra = {}) {
		const raw = gunzipSync(gzip, { maxOutputLength: 256_000_000 });
		const index = entries.length;
		entries.push({
			name,
			kind,
			offset,
			bytes: gzip.length,
			rawBytes: raw.length,
			gzipSha256: sha256(gzip),
			rawSha256: sha256(raw),
			...extra,
		});
		payloads.push(gzip);
		offset += gzip.length;
		return index;
	}
	function extract(value, path = []) {
		if (typeof value === "string" && value.startsWith("gzip:")) {
			const gzip = Buffer.from(value.slice(5), "base64");
			assert.equal(`gzip:${gzip.toString("base64")}`, value);
			return { $binary: add(path.join("/"), "kept", gzip) };
		}
		if (Array.isArray(value))
			return value.map((v, i) => extract(v, [...path, i]));
		if (value && typeof value === "object") {
			assert.ok(!Object.hasOwn(value, "$binary"));
			return Object.fromEntries(
				Object.entries(value).map(([k, v]) => [k, extract(v, [...path, k])]),
			);
		}
		return value;
	}
	const metadata = extract(kept);
	for (const record of graphEntries) {
		assert.equal(sha256(record.gzip), record.gzipSha256);
		const index = add(record.name, "graph", record.gzip, {
			typecode: record.typecode,
			elements: record.elements,
		});
		assert.equal(entries[index].rawSha256, record.rawSha256);
		assert.equal(entries[index].rawBytes, record.rawBytes);
	}
	const descriptor = {
		version: 1,
		kept: metadata,
		entries,
		stats,
		keptJsonSha256: sha256(JSON.stringify(kept)),
		payloadBytes: offset,
	};
	const json = Buffer.from(JSON.stringify(descriptor));
	assert.ok(json.length <= maxDescriptorBytes);
	const header = Buffer.alloc(12);
	magic.copy(header);
	header.writeUInt32LE(json.length, 8);
	return { bytes: Buffer.concat([header, json, ...payloads]), descriptor };
}

export function parseContainer(bytes, expectedSha256) {
	assert.ok(bytes.length >= 12 && bytes.length <= 80_000_000);
	assert.equal(sha256(bytes), expectedSha256, "Binary file SHA differs");
	assert.deepEqual(bytes.subarray(0, 8), magic);
	const length = bytes.readUInt32LE(8);
	assert.ok(
		length > 0 && length <= maxDescriptorBytes && 12 + length <= bytes.length,
	);
	const descriptor = JSON.parse(bytes.toString("utf8", 12, 12 + length));
	assert.equal(descriptor.version, 1);
	assert.ok(
		Array.isArray(descriptor.entries) && descriptor.entries.length <= 64,
	);
	const payload = bytes.subarray(12 + length);
	assert.equal(descriptor.payloadBytes, payload.length);
	let offset = 0;
	const names = new Set();
	for (const entry of descriptor.entries) {
		assert.ok(
			typeof entry.name === "string" && ["kept", "graph"].includes(entry.kind),
		);
		assert.ok(!names.has(`${entry.kind}/${entry.name}`));
		names.add(`${entry.kind}/${entry.name}`);
		assert.equal(entry.offset, offset);
		assert.ok(
			Number.isSafeInteger(entry.bytes) &&
				entry.bytes > 0 &&
				offset + entry.bytes <= payload.length,
		);
		assert.ok(
			Number.isSafeInteger(entry.rawBytes) &&
				entry.rawBytes >= 0 &&
				entry.rawBytes <= 256_000_000,
		);
		if (entry.kind === "graph") {
			assert.ok(Object.hasOwn(typeSizes, entry.typecode));
			assert.ok(Number.isSafeInteger(entry.elements) && entry.elements >= 0);
			assert.equal(entry.rawBytes, entry.elements * typeSizes[entry.typecode]);
		}
		offset += entry.bytes;
	}
	assert.equal(offset, payload.length);
	return { descriptor, payload };
}

export function typedView(raw, typecode) {
	const Type = { B: Uint8Array, I: Uint32Array, d: Float64Array }[typecode];
	assert.ok(Type && raw.length % Type.BYTES_PER_ELEMENT === 0);
	const count = raw.length / Type.BYTES_PER_ELEMENT;
	if (nativeLittleEndian && raw.byteOffset % Type.BYTES_PER_ELEMENT === 0)
		return new Type(raw.buffer, raw.byteOffset, count);
	const result = new Type(count);
	const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
	for (let i = 0; i < count; i++) {
		const offset = i * Type.BYTES_PER_ELEMENT;
		result[i] =
			typecode === "d"
				? view.getFloat64(offset, true)
				: typecode === "I"
					? view.getUint32(offset, true)
					: view.getUint8(offset);
	}
	return result;
}

export function decodeContainer(bytes, expectedSha256) {
	const { descriptor, payload } = parseContainer(bytes, expectedSha256);
	const graph = {};
	for (const entry of descriptor.entries) {
		const gzip = payload.subarray(entry.offset, entry.offset + entry.bytes);
		assert.equal(sha256(gzip), entry.gzipSha256);
		const raw = gunzipSync(gzip, {
			maxOutputLength: Math.max(entry.rawBytes, 1),
		});
		assert.equal(raw.length, entry.rawBytes);
		assert.equal(sha256(raw), entry.rawSha256);
		if (entry.kind === "graph")
			graph[entry.name] = typedView(raw, entry.typecode);
	}
	const used = new Set();
	function restore(value) {
		if (!value || typeof value !== "object") return value;
		if (Object.hasOwn(value, "$binary")) {
			assert.equal(Object.keys(value).length, 1);
			const index = value.$binary;
			assert.ok(
				Number.isSafeInteger(index) &&
					index >= 0 &&
					index < descriptor.entries.length,
			);
			const entry = descriptor.entries[index];
			assert.equal(entry.kind, "kept");
			assert.ok(!used.has(index));
			used.add(index);
			return `gzip:${payload.subarray(entry.offset, entry.offset + entry.bytes).toString("base64")}`;
		}
		for (const key of Object.keys(value)) value[key] = restore(value[key]);
		return value;
	}
	const kept = restore(descriptor.kept);
	assert.equal(
		used.size,
		descriptor.entries.filter((e) => e.kind === "kept").length,
	);
	assert.equal(sha256(JSON.stringify(kept)), descriptor.keptJsonSha256);
	return {
		kept,
		graph,
		stats: descriptor.stats,
		parity: {
			entries: descriptor.entries.length,
			graphArrays: Object.keys(graph).length,
			keptBlobs: used.size,
			keptJsonSha256: descriptor.keptJsonSha256,
			binarySha256: expectedSha256,
			allGzipAndRawHashes: true,
		},
	};
}
