import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
const options = { stage: "build", name: null, source: "experiment-region-v1" };
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (
		option === "--stage" &&
		["calibrate", "build", "rebuild", "qualify", "cuts"].includes(value)
	)
		options.stage = value;
	else if (option === "--run-name" && value) options.name = value;
	else if (option === "--source-run" && /^[a-zA-Z0-9_-]+$/.test(value ?? ""))
		options.source = value;
	else
		throw new Error(
			"Usage: node routing/region-increment.mjs [--stage calibrate|build|rebuild|qualify|cuts] [--run-name name] [--source-run name]",
		);
}
const calibrate = options.stage === "calibrate";
await runOfflineNoSwap({
	directory: calibrate ? "qualification-pilot" : "compact-pilot",
	name:
		options.name ??
		(calibrate
			? "experiment-lean-v1"
			: ["build", "qualify"].includes(options.stage)
				? "experiment-region-v1"
				: `experiment-region-v1-${options.stage}`),
	worker: calibrate ? "regional_qualification.py" : "region_increment.py",
	memory: "4g",
	args: calibrate
		? []
		: ["--stage", options.stage, "--source-run", options.source],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
