import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name" || !args[1]))
	throw new Error("Usage: npm run routing:paged -- [--run-name name]");
await runOfflineNoSwap({
	directory: "resource-pilot",
	name: args[1] ?? "paged-import-v1",
	worker: "paged_import.py",
	memory: "4g",
	args: ["--case", "buffer-v3", "--series", "input-v1"],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
