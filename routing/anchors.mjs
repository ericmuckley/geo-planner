import { runOffline } from "./offline.mjs";
import { manifest } from "./settings.mjs";

const options = {};
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i += 2) {
	if (
		!["--count", "--max-new-rows", "--run-name", "--algorithm"].includes(
			args[i],
		) ||
		!args[i + 1] ||
		Object.hasOwn(options, args[i])
	)
		throw new Error(
			"Usage: npm run routing:anchors -- [--count 32] [--max-new-rows 8] [--run-name name] [--algorithm timedistancematrix|costmatrix]",
		);
	options[args[i]] = args[i + 1];
}
const count = Number(options["--count"] ?? 32);
if (!Number.isInteger(count) || count < 2 || count > 1000)
	throw new Error("--count must be an integer between 2 and 1000");
const maxNewRows = Number(options["--max-new-rows"] ?? count);
if (!Number.isInteger(maxNewRows) || maxNewRows < 0 || maxNewRows > count)
	throw new Error("--max-new-rows must be an integer between 0 and count");
const algorithm = options["--algorithm"] ?? "timedistancematrix";
if (!["timedistancematrix", "costmatrix"].includes(algorithm))
	throw new Error("--algorithm must be timedistancematrix or costmatrix");
const runName = options["--run-name"] ?? `${manifest.id}-${algorithm}-${count}`;
await runOffline({
	directory: "anchor-pilot",
	name: runName,
	worker: "anchors.py",
	args: [
		"--expected-graph",
		manifest.id,
		"--count",
		String(count),
		"--algorithm",
		algorithm,
		"--max-new-rows",
		String(maxNewRows),
	],
});
