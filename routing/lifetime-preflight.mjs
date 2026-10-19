import { resolve } from "node:path";
import { runSparseOffline } from "./offline-sparse.mjs";
import { root } from "./settings.mjs";

const options = {
	case: "calibration",
	name: null,
	calibration: null,
	mode: "isolated",
};
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--mode" && ["isolated", "batched"].includes(value))
		options.mode = value;
	else if (option === "--case" && ["calibration", "candidate"].includes(value))
		options.case = value;
	else if (option === "--run-name" && value) options.name = value;
	else if (
		option === "--calibration-run" &&
		/^[a-zA-Z0-9_-]+$/.test(value ?? "")
	)
		options.calibration = value;
	else
		throw new Error(
			"Usage: npm run routing:lifetime -- [--mode isolated|batched] [--case calibration|candidate] [--run-name name] [--calibration-run name]",
		);
}
await runSparseOffline({
	directory: "coverage-pilot",
	name: options.name ?? `lifetime-${options.mode}-${options.case}-v1`,
	worker: "lifetime_preflight.py",
	memory: "4g",
	args: [
		"--case",
		options.case,
		"--mode",
		options.mode,
		"--calibration-run",
		options.calibration ?? `lifetime-${options.mode}-calibration-v1`,
	],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
