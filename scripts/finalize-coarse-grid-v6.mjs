// Version the qualified 0.05-degree model without altering graph data.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

const [input, output] = process.argv.slice(2);
assert.ok(
	input && output,
	"Pass the resolution candidate and a fresh output path",
);
const raw = await readFile(input);
const sha256 = (value) => createHash("sha256").update(value).digest("hex");
assert.equal(
	sha256(raw),
	"b3e65e43e4377f98c7bd21cc7e458f09f9a7ade78ef8d100b345dd1c14c686df",
);
const data = JSON.parse(raw);
data.version = "natural-earth-census-2026-grid-v6";
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
				"Version-only finalization; every graph/source/notice field is unchanged from the pinned, independently rebuilt 0.05-degree candidate. Existing outputs are never overwritten.",
		},
		null,
		2,
	),
);
