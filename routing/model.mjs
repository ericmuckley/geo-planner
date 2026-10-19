import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error("Usage: npm run routing:model -- [--run-name name]");
await runOffline({
	directory: "model-pilot",
	name: args[1] ?? "downtown-maneuvers-v2",
	worker: "model.py",
	memory: "2g",
	args: ["--reference", "/reference"],
	readOnlyMounts: [
		{
			source: resolve(root, "data/reference-pilot/downtown-static-v1"),
			target: "/reference",
		},
	],
});
