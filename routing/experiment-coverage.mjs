import { resolve } from "node:path";
import { runSparseOffline } from "./offline-sparse.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error(
		"Usage: npm run routing:experiment:coverage -- [--run-name fresh-name]",
	);
await runSparseOffline({
	directory: "coverage-pilot",
	name: args[1] ?? "experiment-increment-v1",
	worker: "experiment_coverage.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
