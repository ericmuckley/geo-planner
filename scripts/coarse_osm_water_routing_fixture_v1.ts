import { createHash } from "node:crypto";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { gzipSync } from "node:zlib";
import { loadWaterRaster } from "./coarse_osm_water_raster_loader_v1.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";

const sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");

export async function waterFixture(
	water: (x: number, y: number) => boolean = () => false,
	uncertain: (x: number, y: number) => boolean = () => false,
	grid = { xE7: -1000000, yE7: -1000000, stepE7: 50000, columns: 40, rows: 40 },
) {
	const root = await mkdtemp(path.join(os.tmpdir(), "geo-water-adapter-"));
	try {
		const cells = grid.columns * grid.rows;
		const plane = async (name: string, selected: typeof water) => {
			const raw = Buffer.alloc(Math.ceil(cells / 8));
			let set = 0;
			for (let y = 0; y < grid.rows; y++)
				for (let x = 0; x < grid.columns; x++)
					if (selected(x, y)) {
						const i = y * grid.columns + x;
						raw[i >>> 3] |= 1 << (i % 8);
						set++;
					}
			const compressed = gzipSync(raw);
			await writeFile(path.join(root, `${name}.bits.gz`), compressed);
			return {
				file: `${name}.bits.gz`,
				rawFile: `${name}.bits`,
				rawBytes: raw.length,
				rawSha256: sha(raw),
				compressedBytes: compressed.length,
				compressedSha256: sha(compressed),
				setCells: set,
			};
		};
		const manifest = {
			format: "exact-water-centers-and-source-uncertainty-v1",
			grid: { ...grid, cells, bitOrder: "row-major-lsb-first" },
			planes: {
				water: await plane("water-center", water),
				uncertainty: await plane("source-uncertainty", uncertain),
			},
			sourceCounts: {
				features: 0,
				rings: 0,
				points: 0,
				excludedFeatures: 0,
				knownExcludedBounds: 0,
			},
			sourceIncompleteFeatures: [],
			sourceGeometryCompletelyBounded: true,
			semantics: "Synthetic routing adapter fixture only.",
		};
		const encoded = Buffer.from(JSON.stringify(manifest));
		await writeFile(path.join(root, "manifest.json"), encoded);
		const pin = sha(encoded);
		return {
			current: await loadWaterRasterV2(root, pin),
			old: await loadWaterRaster(root, pin),
		};
	} finally {
		await rm(root, { recursive: true, force: true });
	}
}
