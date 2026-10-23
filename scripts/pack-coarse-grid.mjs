// Lossless storage only: compress the existing binary arrays, never graph rules.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { gunzipSync, gzipSync } from "node:zlib";

const [input, output] = process.argv.slice(2);
assert.ok(input && output, "Pass a grid JSON and a fresh packed output path");
const raw = await readFile(input);
const data = JSON.parse(raw);
const fields = [];
function pack(object, keys, prefix = "") {
	for (const key of keys) {
		if (!object?.[key]) continue;
		assert.equal(typeof object[key], "string");
		assert.ok(!object[key].startsWith("gzip:"), "Input is already packed");
		const bytes = Buffer.from(object[key], "base64");
		const compressed = gzipSync(bytes, { level: 9 });
		assert.deepEqual(gunzipSync(compressed), bytes);
		const packed = `gzip:${compressed.toString("base64")}`;
		const changed = packed.length < object[key].length;
		fields.push({
			field: prefix + key,
			decodedBytes: bytes.length,
			beforeBytes: object[key].length,
			afterBytes: changed ? packed.length : object[key].length,
			compressed: changed,
		});
		if (changed) object[key] = packed;
	}
}
pack(data, [
	"land",
	"traversable",
	"displayLand",
	"links",
	"roadDeciseconds",
	"anchorOffsets",
	"shoreLinks",
]);
for (const field of ["roadVisits", "supplementalRoadVisits"]) {
	assert.ok(!Array.isArray(data[field]), "Expected packed source visits");
	pack(
		data[field],
		["cells", "speeds", "anchors", "starts", "offsets"],
		`${field}.`,
	);
}
pack(
	data.roadLayer,
	["anchorOffsets", "roadDeciseconds", "transferDeciseconds"],
	"roadLayer.",
);
const packed = `${JSON.stringify(data)}\n`;
await writeFile(output, packed, { flag: "wx" });
const hash = (value) => createHash("sha256").update(value).digest("hex");
console.log(
	JSON.stringify(
		{
			input,
			inputSha256: hash(raw),
			inputBytes: raw.length,
			output,
			outputSha256: hash(packed),
			outputBytes: Buffer.byteLength(packed),
			fields,
			node: process.version,
			zlib: process.versions.zlib,
			scope:
				"Lossless per-array gzip/base64 storage. Every compressed binary array inflates byte-identically; all metadata and graph rules remain unchanged. Existing files are never overwritten. No activation, network, DB or source producer.",
		},
		null,
		2,
	),
);
