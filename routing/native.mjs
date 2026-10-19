import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error("Usage: npm run routing:native -- [--run-name name]");
const name = args[1] ?? "downtown-native-v1";
if (!/^[a-zA-Z0-9_-]+$/.test(name))
	throw new Error("Run names accept letters, numbers, underscores and hyphens");
if (process.platform !== "darwin")
	throw new Error(
		"This benchmark wrapper requires macOS sandbox-exec; see docs/native-routing-baseline.md",
	);
const policy = await readFile(
	resolve(root, "routing/native-network.sb"),
	"utf8",
);
const env = Object.fromEntries(
	[
		"PATH",
		"HOME",
		"TMPDIR",
		"LANG",
		"LC_ALL",
		"DEVELOPER_DIR",
		"SDKROOT",
		"MACOSX_DEPLOYMENT_TARGET",
	]
		.filter((key) => process.env[key] !== undefined)
		.map((key) => [key, process.env[key]]),
);
env.PYTHONDONTWRITEBYTECODE = "1";
const child = spawn(
	"/usr/bin/sandbox-exec",
	[
		"-p",
		policy,
		"python3",
		"-u",
		resolve(root, "routing/native_experiment.py"),
		"--reference",
		resolve(root, "data/reference-pilot/downtown-static-v1"),
		"--output",
		resolve(root, "data/native-pilot", name),
	],
	{ cwd: root, stdio: "inherit", env },
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
