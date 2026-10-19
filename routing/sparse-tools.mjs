import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { root } from "./settings.mjs";

const lockPath = resolve(root, "routing/tools/pyosmium-v1.json");
const lock = JSON.parse(await readFile(lockPath, "utf8"));
const cache = resolve(root, "data/tools/pyosmium-v1");
const context = resolve(root, "data/tools/sparse-build-v1");
const inspect = (name) => {
	const result = spawnSync(
		"docker",
		["image", "inspect", name, "--format", "{{.Id}}"],
		{
			encoding: "utf8",
		},
	);
	if (result.status !== 0) throw new Error(`Missing cached image: ${name}`);
	return result.stdout.trim();
};
if (inspect("geo-planner-valhalla-tools:7fd2228e5") !== lock.baseImageId)
	throw new Error("Cached base image differs from the tooling lock");
await mkdir(resolve(context, "wheels"), { recursive: true });
await mkdir(cache, { recursive: true });
for (const wheel of lock.wheels) {
	const path = resolve(cache, wheel.filename);
	let data;
	try {
		data = await readFile(path);
	} catch (error) {
		if (error.code !== "ENOENT") throw error;
		const response = await fetch(wheel.url);
		if (!response.ok)
			throw new Error(`Wheel download failed: ${wheel.filename}`);
		data = Buffer.from(await response.arrayBuffer());
		if (createHash("sha256").update(data).digest("hex") !== wheel.sha256)
			throw new Error(`Wheel checksum differs: ${wheel.filename}`);
		await writeFile(path, data, { flag: "wx" });
	}
	if (
		data.length !== wheel.bytes ||
		createHash("sha256").update(data).digest("hex") !== wheel.sha256
	)
		throw new Error(`Cached wheel differs: ${wheel.filename}`);
	await copyFile(path, resolve(context, "wheels", wheel.filename));
}
await copyFile(lockPath, resolve(context, "lock.json"));
await copyFile(
	resolve(root, "routing/sparse.Dockerfile"),
	resolve(context, "Dockerfile"),
);
const tag = "geo-planner-osm-sparse:4.3.1-v1";
const built = spawnSync(
	"docker",
	["build", "--pull=false", "--network=none", "-t", tag, context],
	{ stdio: "inherit" },
);
if (built.status !== 0) throw new Error("Offline sparse tools build failed");
const record = {
	imageId: inspect(tag),
	baseImageId: lock.baseImageId,
	wheelsLockSha256: createHash("sha256")
		.update(await readFile(lockPath))
		.digest("hex"),
	dockerfileSha256: createHash("sha256")
		.update(await readFile(resolve(root, "routing/sparse.Dockerfile")))
		.digest("hex"),
};
const recordPath = resolve(root, "data/tools/sparse-image-v1.json");
try {
	const previous = JSON.parse(await readFile(recordPath, "utf8"));
	if (JSON.stringify(previous) !== JSON.stringify(record))
		throw new Error(
			"Preserve the existing tool version; use a new recipe version",
		);
} catch (error) {
	if (error.code !== "ENOENT") throw error;
	await writeFile(recordPath, `${JSON.stringify(record, null, 2)}\n`, {
		flag: "wx",
	});
}
console.log(JSON.stringify(record));
