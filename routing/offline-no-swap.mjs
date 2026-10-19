import { spawn, spawnSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { dataDir, root } from "./settings.mjs";

// Versioned recipe: preserve offline.mjs for historical reproductions.
export async function runOfflineNoSwap({
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
			"geo-planner-valhalla-tools:7fd2228e5",
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
