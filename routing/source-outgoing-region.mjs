import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const options = { stage: "build", name: null };
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--stage" && ["build", "rebuild"].includes(value))
		options.stage = value;
	else if (option === "--run-name" && value) options.name = value;
	else
		throw new Error(
			"Usage: node routing/source-outgoing-region.mjs [--stage build|rebuild] [--run-name fresh-name]",
		);
}
await runOfflineNoSwap({
	directory: "compact-pilot",
	name:
		options.name ??
		`source-outgoing-v1${options.stage === "rebuild" ? "-rebuild" : ""}`,
	worker: "source_outgoing_region.py",
	memory: "4g",
	args: ["--stage", options.stage],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
