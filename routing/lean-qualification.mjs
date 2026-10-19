import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name" || !args[1]))
	throw new Error("Usage: npm run routing:qualify:lean -- [--run-name name]");
await runOfflineNoSwap({
	directory: "qualification-pilot",
	name: args[1] ?? "virtual-sink-v1",
	worker: "lean_qualification.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
