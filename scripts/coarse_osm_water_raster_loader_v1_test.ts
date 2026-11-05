import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { gzipSync } from "node:zlib";
import { loadWaterRaster } from "./coarse_osm_water_raster_loader_v1.ts";

const sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");
const popcount = (v: number) => v.toString(2).replaceAll("0", "").length;

async function fixture(
	root: string,
	grid = { xE7: 0, yE7: 0, stepE7: 10, columns: 5, rows: 3 },
	incomplete = false,
) {
	const cells = grid.columns * grid.rows;
	const descriptor = async (name: string, first: number) => {
		const raw = Buffer.alloc(Math.ceil(cells / 8));
		raw[0] = first;
		const compressed = gzipSync(raw);
		await writeFile(path.join(root, `${name}.bits.gz`), compressed);
		return {
			file: `${name}.bits.gz`,
			rawFile: `${name}.bits`,
			rawBytes: raw.length,
			rawSha256: sha(raw),
			compressedBytes: compressed.length,
			compressedSha256: sha(compressed),
			setCells: popcount(first),
		};
	};
	const manifest = {
		format: "exact-water-centers-and-source-uncertainty-v1",
		grid: { ...grid, cells, bitOrder: "row-major-lsb-first" },
		planes: {
			water: await descriptor("water-center", 5),
			uncertainty: await descriptor("source-uncertainty", 6),
		},
		sourceCounts: {
			features: 1,
			rings: 1,
			points: 4,
			excludedFeatures: incomplete ? 1 : 0,
			knownExcludedBounds: incomplete ? 1 : 0,
		},
		sourceIncompleteFeatures: incomplete
			? [
					{
						kind: 2,
						id: 123,
						rawRelationType: "multipolygon",
						missingSourceWayIds: [456],
						missingSourceRelationIds: [],
					},
				]
			: [],
		sourceGeometryCompletelyBounded: !incomplete,
		semantics: "Test-only data, no land interpretation.",
	};
	return manifest;
}

async function save(root: string, manifest: unknown) {
	const raw = Buffer.from(`${JSON.stringify(manifest)}\n`);
	await writeFile(path.join(root, "manifest.json"), raw);
	return sha(raw);
}

async function temporary(work: (root: string) => Promise<void>) {
	const root = await mkdtemp(path.join(os.tmpdir(), "geo-water-raster-"));
	try {
		await work(root);
	} finally {
		await rm(root, { recursive: true, force: true });
	}
}

test("bits, own buffers, global uncertainty and read-only observations", () =>
	temporary(async (root) => {
		const packet = await loadWaterRaster(
			root,
			await save(root, await fixture(root, undefined, true)),
		);
		assert.equal(packet.backingBytes, 4);
		const a = packet.lookup([0.0000001, 0.0000001]),
			b = packet.lookup([0.0000011, 0.0000001]);
		assert.equal(a.kind, "cell");
		assert.equal(b.kind, "cell");
		if (a.kind === "cell" && b.kind === "cell") {
			assert.equal(a.waterAtCenter, true);
			assert.equal(a.sourceUncertainty, false);
			assert.equal(b.waterAtCenter, false);
			assert.equal(b.sourceUncertainty, true);
		}
		assert.equal(a.sourceGeometryCompletelyBounded, false);
		assert.equal(a.sourceIncompleteFeatureCount, 1);
		assert.equal(packet.lookup([-1, 0]).kind, "outside-grid");
		assert.ok(
			Object.isFrozen(packet.grid) &&
				Object.isFrozen(packet.sourceIncompleteFeatures[0].missingSourceWayIds),
		);
	}));

test("exact decimal grid boundaries and supported-domain edges", () =>
	temporary(async (root) => {
		const grid = {
			xE7: -1250000000,
			yE7: 240000000,
			stepE7: 50000,
			columns: 10,
			rows: 10,
		};
		const packet = await loadWaterRaster(
			root,
			await save(root, await fixture(root, grid)),
		);
		for (const [longitude, column] of [
			[-125, 0],
			[-124.995, 1],
			[-124.995000000001, 0],
			[-124.994999999999, 1],
		] as const) {
			const observation = packet.lookup([longitude, 24]);
			assert.equal(observation.kind, "cell");
			if (observation.kind === "cell") assert.equal(observation.column, column);
		}
		assert.equal(packet.lookup([-124.95, 24]).kind, "outside-grid");
		assert.equal(packet.lookup([-125, 24.05]).kind, "outside-grid");
		const last = packet.lookup([-125, 24.049999999999]);
		assert.equal(last.kind, "cell");
		if (last.kind === "cell") assert.equal(last.row, 9);
	}));

test("scientific notation, subnormal negatives and odd E7 steps", () =>
	temporary(async (root) => {
		const packet = await loadWaterRaster(
			root,
			await save(
				root,
				await fixture(root, { xE7: 0, yE7: 0, stepE7: 3, columns: 5, rows: 3 }),
			),
		);
		assert.equal(packet.lookup([-Number.MIN_VALUE, 0]).kind, "outside-grid");
		const a = packet.lookup([3e-7, 1e-7]);
		assert.equal(a.kind, "cell");
		if (a.kind === "cell") {
			assert.equal(a.column, 1);
			assert.deepEqual(a.centerE7, [4.5, 1.5]);
		}
	}));

test("manifest pin, format, grid, incomplete-source and file-path corruption", () =>
	temporary(async (root) => {
		const base = await fixture(root);
		await assert.rejects(loadWaterRaster(root, "0".repeat(64)));
		for (const mutate of [
			(m: typeof base) => {
				m.format = "wrong";
			},
			(m: typeof base) => {
				m.grid.cells++;
			},
			(m: typeof base) => {
				m.grid.stepE7 = 0;
			},
			(m: typeof base) => {
				m.sourceGeometryCompletelyBounded = false;
			},
			(m: typeof base) => {
				m.planes.water.file = "../secret";
			},
			(m: typeof base) => {
				m.planes.water.rawBytes++;
			},
		]) {
			const broken = structuredClone(base);
			mutate(broken);
			await assert.rejects(loadWaterRaster(root, await save(root, broken)));
		}
	}));

test("compressed and decoded hashes/counts, malformed gzip and padding", () =>
	temporary(async (root) => {
		for (const mode of ["compressed", "raw-hash", "count", "gzip", "padding"]) {
			const manifest = await fixture(root);
			if (mode === "compressed")
				manifest.planes.water.compressedSha256 = "0".repeat(64);
			else if (mode === "raw-hash")
				manifest.planes.water.rawSha256 = "0".repeat(64);
			else if (mode === "count") manifest.planes.water.setCells++;
			else {
				const raw =
					mode === "padding" ? Buffer.from([5, 128]) : Buffer.from("not-gzip");
				const compressed = mode === "padding" ? gzipSync(raw) : raw;
				await writeFile(path.join(root, "water-center.bits.gz"), compressed);
				Object.assign(manifest.planes.water, {
					rawSha256: sha(raw),
					compressedBytes: compressed.length,
					compressedSha256: sha(compressed),
					setCells: 3,
				});
			}
			await assert.rejects(loadWaterRaster(root, await save(root, manifest)));
		}
	}));

test("symlinked/truncated files and invalid numeric coordinates", () =>
	temporary(async (root) => {
		const manifest = await fixture(root),
			pin = await save(root, manifest),
			filename = path.join(root, "water-center.bits.gz");
		const raw = await readFile(filename);
		await writeFile(filename, raw.subarray(0, raw.length - 1));
		await assert.rejects(loadWaterRaster(root, pin));
		await writeFile(path.join(root, "other.gz"), raw);
		await rm(filename);
		await symlink("other.gz", filename);
		await assert.rejects(loadWaterRaster(root, pin));
		await rm(filename);
		await writeFile(filename, raw);
		const packet = await loadWaterRaster(root, pin);
		for (const coordinate of [
			[NaN, 0],
			[Infinity, 0],
			[181, 0],
			[0, -91],
		] as const)
			assert.throws(() => packet.lookup(coordinate));
	}));
