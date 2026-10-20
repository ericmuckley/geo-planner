import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const options = { stage: "build", name: null, source: "two-hour-region-v2" };
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--stage" && ["calibrate", "build", "rebuild"].includes(value))
		options.stage = value;
	else if (option === "--run-name" && value) options.name = value;
	else if (option === "--source-run" && /^[a-zA-Z0-9_-]+$/.test(value ?? ""))
		options.source = value;
	else
		throw new Error(
			"Usage: node routing/scoped-region.mjs [--stage calibrate|build|rebuild] [--run-name fresh-name] [--source-run name]",
		);
}
await runOfflineNoSwap({
	directory: "compact-pilot",
	name:
		options.name ??
		(options.stage === "calibrate"
			? "scoped-current-v1"
			: options.stage === "build"
				? "two-hour-region-v2"
				: "two-hour-region-v2-rebuild"),
	worker: "scoped_region.py",
	memory: "4g",
	args: ["--stage", options.stage, "--source-run", options.source],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
