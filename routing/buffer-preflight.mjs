import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const options = {
	case: "calibration",
	name: null,
	calibration: "staged-calibration-v2-r4",
};
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--case" && ["calibration", "candidate"].includes(value))
		options.case = value;
	else if (option === "--run-name" && value) options.name = value;
	else if (
		option === "--calibration-run" &&
		value &&
		/^[a-zA-Z0-9_-]+$/.test(value)
	)
		options.calibration = value;
	else
		throw new Error(
			"Usage: npm run routing:coverage:next -- [--case calibration|candidate] [--run-name name] [--calibration-run name]",
		);
}
await runOfflineNoSwap({
	directory: "coverage-pilot",
	name:
		options.name ??
		(options.case === "calibration"
			? options.calibration
			: "staged-candidate-v2"),
	worker: "buffer_preflight.py",
	memory: "4g",
	args: ["--case", options.case, "--calibration-run", options.calibration],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
