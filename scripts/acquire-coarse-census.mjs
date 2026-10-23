import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createReadStream, createWriteStream } from "node:fs";
import {
	access,
	link,
	mkdir,
	readFile,
	stat,
	unlink,
	writeFile,
} from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";

const catalogUrl = "https://www2.census.gov/geo/tiger/TIGER2026/PRISECROADS/";
const cache = "data/coarse-sources/tiger-2026";
const directory = process.argv[2];
const download = process.argv.includes("--download");
assert.ok(directory, "Pass a new manifest directory, optionally --download");
assert.ok(
	resolve(directory).startsWith(`${resolve(cache)}/`),
	"Keep source manifests in the ignored cache",
);
await mkdir(directory, { recursive: true });
const exists = async (path) =>
	access(path).then(
		() => true,
		() => false,
	);
const manifestPath = join(directory, "sources.json");
const pinned = (await exists(manifestPath))
	? JSON.parse(await readFile(manifestPath, "utf8"))
	: undefined;
const expectedSources = new Map(
	pinned?.sources.map((source) => [source.url, source]),
);
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const catalogPath = join(directory, "catalog.html");
if (!(await exists(catalogPath))) {
	assert.ok(download, "Missing catalog: use --download for acquisition");
	const response = await fetch(catalogUrl, {
		signal: AbortSignal.timeout(30000),
	});
	assert.ok(response.ok, `Census catalog HTTP ${response.status}`);
	await writeFile(catalogPath, await response.text(), { flag: "wx" });
}
const catalog = await readFile(catalogPath);
const files = [
	...new Set(
		[
			...catalog
				.toString()
				.matchAll(/href="(tl_2026_(\d{2})_prisecroads\.zip)"/g),
		]
			// FIPS scope selection is offline only: exclude Alaska, Hawaii, territories.
			.filter((m) => Number(m[2]) < 60 && !["02", "15"].includes(m[2]))
			.map((m) => m[1]),
	),
].sort();
assert.equal(files.length, 49, "Expected 48 contiguous states plus DC");
const sources = new Array(files.length);
let next = 0;
let downloadedBytes = 0;
let downloadedFiles = 0;
async function worker() {
	while (next < files.length) {
		const index = next++;
		const filename = files[index];
		const path = join(cache, filename);
		const lockPath = path.replace(/\.zip$/, ".source.json");
		const url = new URL(filename, catalogUrl).href;
		if (await exists(path)) {
			const lock = (await exists(lockPath))
				? JSON.parse(await readFile(lockPath, "utf8"))
				: expectedSources.get(url);
			assert.ok(lock, `Cached source has no pinned lock: ${path}`);
			assert.equal(lock.url, url);
			assert.equal(lock.path, path);
			assert.equal((await stat(path)).size, lock.bytes);
			const hash = createHash("sha256");
			for await (const chunk of createReadStream(path)) hash.update(chunk);
			assert.equal(
				hash.digest("hex"),
				lock.sha256,
				`Cached source changed: ${path}`,
			);
			if (pinned) assert.deepEqual(lock, expectedSources.get(url));
			if (!(await exists(lockPath)))
				await writeFile(lockPath, `${JSON.stringify(lock, null, 2)}\n`, {
					flag: "wx",
				});
			sources[index] = lock;
			console.error(`Verified ${index + 1}/${files.length}: ${filename}`);
			continue;
		}
		assert.ok(
			download,
			`Missing source: ${path}; acquisition requires --download`,
		);
		assert.ok(
			!(await exists(lockPath)),
			`Source lock exists without its ZIP: ${lockPath}`,
		);
		const response = await fetch(url, { signal: AbortSignal.timeout(180000) });
		assert.ok(
			response.ok && response.body,
			`Census source HTTP ${response.status}: ${filename}`,
		);
		const partial = `${path}.${Date.now()}.partial`;
		const hash = createHash("sha256");
		let bytes = 0;
		const observe = new Transform({
			transform(chunk, _encoding, callback) {
				hash.update(chunk);
				bytes += chunk.length;
				callback(null, chunk);
			},
		});
		await pipeline(
			Readable.fromWeb(response.body),
			observe,
			createWriteStream(partial, { flags: "wx" }),
		);
		const length = response.headers.get("content-length");
		if (length !== null) assert.equal(bytes, Number(length));
		assert.ok(bytes > 0);
		const lock = { url, path, bytes, sha256: hash.digest("hex") };
		if (pinned) assert.deepEqual(lock, expectedSources.get(url));
		await link(partial, path); // Refuse replacement even if another process wrote it.
		await unlink(partial);
		await writeFile(lockPath, `${JSON.stringify(lock, null, 2)}\n`, {
			flag: "wx",
		});
		sources[index] = lock;
		downloadedBytes += bytes;
		downloadedFiles++;
		console.error(
			`Downloaded ${index + 1}/${files.length}: ${filename} (${bytes} bytes)`,
		);
	}
}
await Promise.all([worker(), worker()]);
const manifest = {
	release: "TIGER/Line 2026",
	scope: "48 contiguous states plus District of Columbia",
	catalog: {
		url: catalogUrl,
		path: relative(process.cwd(), catalogPath),
		bytes: catalog.length,
		sha256: sha256(catalog),
	},
	sources,
};
if (await exists(manifestPath))
	assert.deepEqual(JSON.parse(await readFile(manifestPath, "utf8")), manifest);
else
	await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, {
		flag: "wx",
	});
console.log(
	JSON.stringify(
		{
			manifest: manifestPath,
			partitions: sources.length,
			sourceBytes: sources.reduce((sum, source) => sum + source.bytes, 0),
			downloadedFiles,
			downloadedBytes,
			scope:
				"Public offline source acquisition/verification only; no routing provider, database or production deployment.",
		},
		null,
		2,
	),
);
