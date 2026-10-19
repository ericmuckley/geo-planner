import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error("Usage: npm run routing:cells -- [--run-name name]");
await runOffline({
	directory: "cell-pilot",
	name: args[1] ?? "downtown-cells-v1",
	worker: "cell_experiment.py",
	args: [],
	readOnlyMounts: [
		{
			source: resolve(root, "data/reference-pilot/downtown-static-v1"),
			target: "/reference",
		},
	],
});
