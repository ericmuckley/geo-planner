import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
const options = { stage: "calibrate", name: null };
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--stage" && ["calibrate", "qualify"].includes(value))
		options.stage = value;
	else if (option === "--run-name" && value) options.name = value;
	else
		throw new Error(
			"Usage: node routing/region-verify.mjs [--stage calibrate|qualify] [--run-name name]",
		);
}
await runOfflineNoSwap({
	directory:
		options.stage === "calibrate" ? "qualification-pilot" : "compact-pilot",
	name:
		options.name ??
		(options.stage === "calibrate"
			? "experiment-ranged-v1"
			: "experiment-region-v1"),
	worker: "region_verification.py",
	memory: "4g",
	args: ["--stage", options.stage],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
