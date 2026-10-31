import assert from "node:assert/strict";
import { test } from "node:test";
import { gzipSync } from "node:zlib";
import {
	decodeContainer,
	encodeContainer,
	parseContainer,
	sha256,
	typedView,
} from "./backbone-binary-format.mjs";
import { roundEven, validateBackbone } from "./backbone-binary-validate.mjs";

function fixture() {
	const kept = {
		bounds: [0, 0, 1, 1],
		width: 1,
		height: 1,
		censusRoadSpeedsKph: { S1100: 105, S1200: 85 },
		land: `gzip:${gzipSync(Buffer.from([1, 0, 1])).toString("base64")}`,
		metadata: { exact: [1.2, null, "hello"] },
	};
	const graph = {
		nodeCoordinates: new Float64Array([0.1, 0.1, 0.2, 0.1]),
		arcFrom: new Uint32Array([0]),
		arcTo: new Uint32Array([1]),
		arcRoadKm: new Float64Array([1]),
		arcMinutes: new Float64Array([1]),
		arcSpeedKph: new Uint8Array([85]),
		arcByteOffsets: new Uint32Array([0, 0]),
		arcInteriorOffsets: new Uint32Array([0, 0]),
		interiorSourceKm: new Float64Array(),
		geometryBytes: new Uint8Array(),
		partArcOffsets: new Uint32Array([0, 1]),
		endpointAdjOffsets: new Uint32Array([0, 1, 2]),
		endpointAdjArcs: new Uint32Array([0, 0]),
		crossingFirstArc: new Uint32Array(),
		cellIds: new Uint32Array([0]),
		cellArcOffsets: new Uint32Array([0, 1]),
		cellArcs: new Uint32Array([0]),
	};
	const entries = Object.entries(graph).map(([name, value]) => {
		const raw = Buffer.from(value.buffer, value.byteOffset, value.byteLength),
			gzip = gzipSync(raw);
		return {
			name,
			gzip,
			gzipSha256: sha256(gzip),
			rawSha256: sha256(raw),
			rawBytes: raw.length,
			elements: value.length,
			typecode:
				value instanceof Float64Array
					? "d"
					: value instanceof Uint32Array
						? "I"
						: "B",
		};
	});
	return {
		kept,
		graph,
		stats: { nodes: 2, arcs: 1, originalNodes: 2, parts: 1 },
		entries,
	};
}

test("container restores every kept value and typed graph byte exactly", () => {
	const source = fixture(),
		packed = encodeContainer(source.kept, source.entries, source.stats);
	const restored = decodeContainer(packed.bytes, sha256(packed.bytes));
	assert.deepEqual(restored.kept, source.kept);
	for (const [name, values] of Object.entries(source.graph))
		assert.deepEqual(restored.graph[name], values);
	assert.equal(restored.parity.keptBlobs, 1);
	assert.equal(
		validateBackbone(restored.graph, restored.stats, restored.kept).nodes,
		2,
	);
});

test("modified bytes fail the externally pinned file hash", () => {
	const source = fixture(),
		packed = encodeContainer(source.kept, source.entries, source.stats);
	const hash = sha256(packed.bytes);
	packed.bytes[packed.bytes.length - 1] ^= 1;
	assert.throws(() => decodeContainer(packed.bytes, hash));
});

test("bad magic, oversized header, overlapping entries and trailing payload fail", () => {
	const source = fixture(),
		packed = encodeContainer(source.kept, source.entries, source.stats);
	const wrongMagic = Buffer.from(packed.bytes);
	wrongMagic[0] = 0;
	assert.throws(() => parseContainer(wrongMagic, sha256(wrongMagic)));
	const wrongLength = Buffer.from(packed.bytes);
	wrongLength.writeUInt32LE(2_000_000, 8);
	assert.throws(() => parseContainer(wrongLength, sha256(wrongLength)));
	const parsed = parseContainer(packed.bytes, sha256(packed.bytes));
	parsed.descriptor.entries[1].offset = 0;
	const descriptor = Buffer.from(JSON.stringify(parsed.descriptor)),
		header = Buffer.from(packed.bytes.subarray(0, 12));
	header.writeUInt32LE(descriptor.length, 8);
	const overlap = Buffer.concat([header, descriptor, parsed.payload]);
	assert.throws(() => parseContainer(overlap, sha256(overlap)));
	const trailing = Buffer.concat([packed.bytes, Buffer.from([0])]);
	assert.throws(() => parseContainer(trailing, sha256(trailing)));
});

test("raw checksum mismatch is caught even with a valid enclosing hash", () => {
	const source = fixture(),
		packed = encodeContainer(source.kept, source.entries, source.stats);
	const parsed = parseContainer(packed.bytes, sha256(packed.bytes));
	parsed.descriptor.entries[0].rawSha256 = "0".repeat(64);
	const json = Buffer.from(JSON.stringify(parsed.descriptor)),
		header = Buffer.from(packed.bytes.subarray(0, 12));
	header.writeUInt32LE(json.length, 8);
	const bytes = Buffer.concat([header, json, parsed.payload]);
	assert.throws(() => decodeContainer(bytes, sha256(bytes)));
});

test("unaligned typed data uses the same little-endian numeric values", () => {
	const raw = Buffer.alloc(17);
	raw.writeDoubleLE(123.25, 1);
	raw.writeDoubleLE(-0.5, 9);
	assert.deepEqual([...typedView(raw.subarray(1), "d")], [123.25, -0.5]);
	assert.throws(() => typedView(Buffer.alloc(3), "I"));
});

test("graph format rejects dangling nodes, nonfinite weights and bad sparse indexes", () => {
	for (const change of [
		(g) => {
			g.arcTo[0] = 3;
		},
		(g) => {
			g.arcMinutes[0] = Number.NaN;
		},
		(g) => {
			g.endpointAdjArcs[0] = 1;
		},
		(g) => {
			g.cellArcs[0] = 1;
		},
		(g) => {
			g.arcInteriorOffsets[1] = 1;
		},
	]) {
		const { graph, stats, kept } = fixture();
		change(graph);
		assert.throws(() => validateBackbone(graph, stats, kept));
	}
});

test("geometry seed rounding matches source ties-to-even for both signs", () => {
	assert.deepEqual(
		[2.5, 3.5, -1.5, -2.5, -0.5, 2.4].map(roundEven),
		[2, 4, -2, -2, 0, 2],
	);
});
