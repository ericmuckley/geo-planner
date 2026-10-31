import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { pathToFileURL } from "node:url";
import { rolldown } from "rolldown";
import {
	backboneAssetId,
	backboneBinaryAsset,
} from "./backbone-binary-asset.mjs";

test("final bundler emits exact binary bytes and a Node file URL", async () => {
	const root = await mkdtemp(join(tmpdir(), "geo-binary-fixture-"));
	const bytes = Buffer.from([0, 255, 128, 1, 2, 0, 10]);
	await writeFile(join(root, "fixture.bin"), bytes);
	await writeFile(
		join(root, "entry.mjs"),
		`export { default } from ${JSON.stringify(backboneAssetId)};`,
	);
	const build = await rolldown({
		input: join(root, "entry.mjs"),
		platform: "node",
		plugins: [backboneBinaryAsset(join(root, "fixture.bin"))],
	});
	await build.write({
		dir: join(root, "out"),
		format: "esm",
		entryFileNames: "index.mjs",
	});
	await build.close();
	const module = await import(pathToFileURL(join(root, "out/index.mjs")).href);
	assert.equal(module.default.protocol, "file:");
	assert.deepEqual(await readFile(module.default), bytes);
	const source = await readFile(join(root, "out/index.mjs"), "utf8");
	assert.ok(!source.includes(bytes.toString("base64")));
});
