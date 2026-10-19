import { resolve } from "node:path";
import { runSparseOffline } from "./offline-sparse.mjs";
import { root } from "./settings.mjs";

const options = {
	case: "calibration",
	name: null,
	calibration: "sparse-calibration-v1",
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
			"Usage: npm run routing:sparse -- [--case calibration|candidate] [--run-name name] [--calibration-run name]",
		);
}
await runSparseOffline({
	directory: "sparse-pilot",
	name: options.name ?? `sparse-${options.case}-v1`,
	worker: "sparse_prepare.py",
	memory: "4g",
	args: ["--case", options.case, "--calibration-run", options.calibration],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
