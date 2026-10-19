import { mkdir, statfs, writeFile } from "node:fs/promises";
import { dataDir, manifest } from "./settings.mjs";

await mkdir(dataDir, { recursive: true });
const disk = await statfs(dataDir);
const freeBytes = disk.bavail * disk.bsize;
const minimumBytes = manifest.minimumFreeDiskBytes || 10 * 1024 ** 3;
if (freeBytes < minimumBytes)
	throw new Error(
		`Graph build needs at least ${minimumBytes} bytes free; found ${freeBytes}.`,
	);
await writeFile(`${dataDir}/manifest.json`, JSON.stringify(manifest, null, 2));
console.log(
	`Graph ${manifest.id}; data ${dataDir}; available disk ${(freeBytes / 1024 ** 3).toFixed(1)} GiB`,
);
