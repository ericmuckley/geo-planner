// Version the qualified road-state model without altering graph data.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

const [input, output] = process.argv.slice(2);
assert.ok(
	input && output,
	"Pass the road-layer candidate and a fresh output path",
);
const raw = await readFile(input);
const sha256 = (value) => createHash("sha256").update(value).digest("hex");
assert.equal(
	sha256(raw),
	"d2f220d90d3d27caaf6d19aab63e2fb0365ea3f29a06398be3ff365b921c3c73",
);
const data = JSON.parse(raw);
data.version = "natural-earth-census-2026-grid-v7";
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
				"Version-only finalization of the pinned, independently rebuilt additive Census road-state model. Every graph/source/notice field remains unchanged; existing outputs are never overwritten.",
		},
		null,
		2,
	),
);
