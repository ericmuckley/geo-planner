import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error(
		"Usage: node routing/base-memory-profile.mjs [--run-name fresh-name]",
	);
await runOfflineNoSwap({
	directory: "resource-pilot",
	name: args[1] ?? "two-hour-base-owners-v1",
	worker: "base_memory_profile.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
