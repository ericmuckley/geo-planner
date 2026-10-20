import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const options = { stage: "calibrate", name: null };
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--stage" && ["calibrate", "candidate"].includes(value))
		options.stage = value;
	else if (option === "--run-name" && value) options.name = value;
	else
		throw new Error(
			"Usage: node routing/scoped-region-cuts.mjs [--stage calibrate|candidate] [--run-name fresh-name]",
		);
}
const calibrate = options.stage === "calibrate";
await runOfflineNoSwap({
	directory: "compact-pilot",
	name:
		options.name ??
		(calibrate
			? "experiment-region-v1-cuts-streamed"
			: "two-hour-region-v2-cuts"),
	worker: "regional_cuts.py",
	memory: "4g",
	args: [
		"--graph-run",
		calibrate ? "experiment-region-v1" : "two-hour-region-v2",
		"--preparation-run",
		calibrate ? "experiment-increment-v1" : "two-hour-region-v2",
		...(calibrate ? ["--compare-run", "experiment-region-v1-cuts"] : []),
	],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
