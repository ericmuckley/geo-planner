// Version the qualified national geometry with product source notices only.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

const [input, output] = process.argv.slice(2);
assert.ok(
	input && output,
	"Pass the national-v2 artifact and a fresh output path",
);
const raw = await readFile(input);
const sha256 = (value) => createHash("sha256").update(value).digest("hex");
assert.equal(
	sha256(raw),
	"119a463d0a876bc83761efb235e1a8a7d9f9105c990b720c9751699c7076b95d",
);
const original = JSON.parse(raw);
const metadata = {
	version: "natural-earth-census-2026-grid-v5",
	sourceRelease:
		"Natural Earth v5.1.2 + U.S. Census Bureau 2026 TIGER/Line primary and secondary roads; derived coarse grid, not a routable road inventory",
	license:
		"Natural Earth: public domain. U.S. Census Bureau TIGER/Line: U.S. government work, freely reproducible; TIGER/Line is a registered trademark of the U.S. Census Bureau.",
	attribution:
		"Made with Natural Earth and U.S. Census Bureau 2026 TIGER/Line data. Geo Planner has modified and repackaged Census data into a coarse travel model. This product is not an official Census Bureau product; the Census Bureau has not reviewed or endorsed these estimates.",
	augmentationModel: original.augmentationModel.replace(
		"Offline candidate, not activated.",
		"Nationwide v5 coarse model; travel-time accuracy remains unvalidated.",
	),
};
const result = { ...original, ...metadata };
const bytes = `${JSON.stringify(result)}\n`;
await writeFile(output, bytes, { flag: "wx" });
console.log(
	JSON.stringify(
		{
			input,
			inputSha256: sha256(raw),
			output,
			outputSha256: sha256(bytes),
			outputBytes: Buffer.byteLength(bytes),
			changedFields: Object.keys(metadata),
			scope:
				"Metadata-only version/source/derived-data notices. Every graph, speed, mask, anchor, geometry and source-lock field is unchanged from the hash-pinned national-v2 artifact. Existing outputs are never overwritten.",
		},
		null,
		2,
	),
);
