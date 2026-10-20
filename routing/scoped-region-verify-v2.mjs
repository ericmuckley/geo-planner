import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error(
		"Usage: node routing/scoped-region-verify-v2.mjs [--run-name built-run-name]",
	);
await runOfflineNoSwap({
	directory: "compact-pilot",
	name: args[1] ?? "two-hour-region-v2",
	worker: "scoped_region_verification_v2.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
