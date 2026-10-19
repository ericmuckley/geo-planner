import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name" || !args[1]))
	throw new Error("Usage: npm run routing:cuts -- [--run-name name]");
await runOfflineNoSwap({
	directory: "coverage-pilot",
	name: args[1] ?? "buffer-cut-inventory-v1",
	worker: "cut_inventory.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
