import { resolve } from "node:path";
import { runSparseOffline } from "./offline-sparse.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error(
		"Usage: node routing/six-hour-prepare.mjs [--run-name fresh-name]",
	);
await runSparseOffline({
	directory: "coverage-pilot",
	name: args[1] ?? "six-hour-cached-v1",
	worker: "six_hour_prepare.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
