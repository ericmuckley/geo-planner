import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { dataDir, root } from "./settings.mjs";

// Separate pinned reader image; preserve historical wrappers.
export async function runSparseOffline({
	directory,
	name,
	worker,
	args,
	memory = "2g",
	readOnlyMounts = [],
}) {
	if (!/^[a-zA-Z0-9_-]+$/.test(name))
		throw new Error(
			"Run names accept letters, numbers, underscores and hyphens",
		);
	const inspected = spawnSync(
		"docker",
		[
			"image",
			"inspect",
			"geo-planner-osm-sparse:4.3.1-v1",
			"--format",
			"{{.Id}}",
		],
		{ encoding: "utf8" },
	);
	if (inspected.status !== 0)
		throw new Error(
			"Cached tools image missing. See docs/offline-anchor-pilot.md.",
		);
	const imageId = inspected.stdout.trim();
	const imageRecord = JSON.parse(
		await readFile(resolve(root, "data/tools/sparse-image-v1.json"), "utf8"),
	);
	const lockSha = createHash("sha256")
		.update(await readFile(resolve(root, "routing/tools/pyosmium-v1.json")))
		.digest("hex");
	if (
		imageId !== imageRecord.imageId ||
		lockSha !== imageRecord.wheelsLockSha256
	)
		throw new Error(
			"Sparse image/lock differs; run routing:tools:sparse with the recorded version",
		);
	const output = resolve(root, "data", directory, name);
	await mkdir(output, { recursive: true });
	const child = spawn(
		"docker",
		[
			"run",
			"--rm",
			"--pull",
			"never",
			"--network",
			"none",
			"--read-only",
			"--tmpfs",
			"/tmp:rw,size=256m",
			"--memory",
			memory,
			"--memory-swap",
			memory,
			"--cpus",
			"2",
			"--mount",
			`type=bind,source=${dataDir},target=/data,readonly`,
			"--mount",
			`type=bind,source=${resolve(root, "routing")},target=/recipe,readonly`,
			"--mount",
			`type=bind,source=${output},target=/output`,
			...readOnlyMounts.flatMap(({ source, target }) => [
				"--mount",
				`type=bind,source=${source},target=${target},readonly`,
			]),
			"--entrypoint",
			"python3",
			imageId,
			"-u",
			`/recipe/${worker}`,
			"--image-id",
			imageId,
			"--base-image-id",
			imageRecord.baseImageId,
			...args,
		],
		{ stdio: "inherit" },
	);
	child.on("error", (error) => {
		console.error(error.message);
		process.exitCode = 1;
	});
	child.on("exit", (code) => {
		process.exitCode = code ?? 1;
	});
	for (const signal of ["SIGINT", "SIGTERM"])
		process.on(signal, () => child.kill(signal));
}
