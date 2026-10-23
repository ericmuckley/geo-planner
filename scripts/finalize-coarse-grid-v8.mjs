// Version the qualified finer-grid model without altering graph data.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

const [input, output] = process.argv.slice(2);
assert.ok(
	input && output,
	"Pass the finer-grid candidate and a fresh output path",
);
const raw = await readFile(input);
const sha256 = (value) => createHash("sha256").update(value).digest("hex");
assert.equal(
	sha256(raw),
	"f5dd46f223fc4a6d601235adc4c59cb8a31326aa416c6fe0da522e34a14dbb5a",
);
const data = JSON.parse(raw);
data.version = "natural-earth-census-2026-grid-v8";
const bytes = `${JSON.stringify(data)}\n`;
await writeFile(output, bytes, { flag: "wx" });
console.log(
	JSON.stringify(
		{
			input,
			inputSha256: sha256(raw),
			output,
			outputSha256: sha256(bytes),
			outputBytes: Buffer.byteLength(bytes),
			changedFields: ["version"],
			scope:
				"Version-only finalization of the pinned, independently rebuilt 0.025-degree model with Census road states and lossless packed arrays. Every graph/source/notice field remains unchanged; existing outputs are never overwritten.",
		},
		null,
		2,
	),
);
