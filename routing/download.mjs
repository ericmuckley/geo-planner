import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, rename, stat, writeFile } from "node:fs/promises";
import { dataDir, manifest, sourceDir } from "./settings.mjs";

const sources = sourceDir;
await mkdir(sources, { recursive: true });
await mkdir(dataDir, { recursive: true });
const verified = [];
for (const source of [
	...manifest.sources,
	...(manifest.adminSupplements || []),
]) {
	const path = `${sources}/${source.file}`;
	if (!(await stat(path).catch(() => null))) {
		console.log(`Downloading ${source.file}: ${source.bytes} bytes`);
		const result = spawnSync(
			"curl",
			[
				"--fail",
				"--location",
				"--compressed",
				"--retry",
				"3",
				"--max-filesize",
				String(source.bytes),
				"--output",
				`${path}.part`,
				source.url,
			],
			{ stdio: "inherit" },
		);
		if (result.status !== 0) throw new Error(`Download failed: ${source.file}`);
		await rename(`${path}.part`, path);
	}
	const md5 = createHash("md5");
	const sha256 = createHash("sha256");
	for await (const chunk of createReadStream(path)) {
		md5.update(chunk);
		sha256.update(chunk);
	}
	const hash = sha256.digest("hex");
	if (
		(await stat(path)).size !== source.bytes ||
		(source.md5 && md5.digest("hex") !== source.md5) ||
		(source.sha256 && hash !== source.sha256)
	) {
		throw new Error(
			`Checksum/size mismatch: ${path}. Preserve or remove it before retrying.`,
		);
	}
	verified.push({ ...source, sha256: hash });
	console.log(`Verified ${source.file}: sha256 ${hash}`);
}
await writeFile(
	`${dataDir}/sources-verified.json`,
	JSON.stringify(
		{
			id: manifest.id,
			verifiedAt: new Date().toISOString(),
			sources: verified,
		},
		null,
		2,
	),
);
