import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const options = {
	case: "downtown-v2",
	series: "base-ids-v1",
	name: null,
	idMode: "ordered",
};
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (
		option === "--case" &&
		["downtown-v2", "corridor-v3", "wide-v3", "hour-v3"].includes(value)
	)
		options.case = value;
	else if (option === "--series" && /^[a-zA-Z0-9_-]+$/.test(value ?? ""))
		options.series = value;
	else if (option === "--id-mode" && ["ordered", "strings"].includes(value))
		options.idMode = value;
	else if (option === "--run-name" && value) options.name = value;
	else
		throw new Error(
			"Usage: npm run routing:base-ids -- [--case downtown-v2|corridor-v3|wide-v3|hour-v3] [--series name] [--run-name name] [--id-mode ordered|strings]",
		);
}
await runOfflineNoSwap({
	directory: "base-id-pilot",
	name: options.name ?? `${options.series}-${options.case}`,
	worker: "base_id_parity.py",
	memory: "4g",
	args: [
		"--case",
		options.case,
		"--series",
		options.series,
		"--id-mode",
		options.idMode,
	],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
