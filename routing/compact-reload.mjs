import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name" || !args[1]))
	throw new Error("Usage: npm run routing:compact:reload -- [--run-name name]");
await runOffline({
	directory: "compact-pilot",
	name: args[1] ?? "compact-v1-buffer-reload",
	worker: "compact_reload.py",
	memory: "1g",
	args: [],
	readOnlyMounts: [
		{
			source: resolve(root, "data/compact-pilot/compact-v1-buffer-v3"),
			target: "/source",
		},
	],
});
