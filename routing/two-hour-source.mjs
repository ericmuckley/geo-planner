import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root, sourceDir } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error(
		"Usage: node routing/two-hour-source.mjs [--run-name fresh-name]",
	);
await runOfflineNoSwap({
	directory: "source-pilot",
	name: args[1] ?? "two-hour-parent-v1",
	worker: "two_hour_source.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [
		{ source: resolve(root, "data"), target: "/inputs" },
		{ source: sourceDir, target: "/sources" },
	],
});
