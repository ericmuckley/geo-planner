import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { sourceDir } from "./settings.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error(
		"Usage: node routing/six-hour-source.mjs [--run-name fresh-name]",
	);
await runOfflineNoSwap({
	directory: "source-pilot",
	name: args[1] ?? "six-hour-cached-v1",
	worker: "six_hour_source.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [{ source: sourceDir, target: "/sources" }],
});
