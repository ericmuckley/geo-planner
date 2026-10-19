import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const options = { stage: "build", name: null, source: "hour-v3" };
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (
		option === "--stage" &&
		["build", "rebuild", "qualify", "cuts"].includes(value)
	)
		options.stage = value;
	else if (option === "--run-name" && value) options.name = value;
	else if (option === "--source-run" && /^[a-zA-Z0-9_-]+$/.test(value ?? ""))
		options.source = value;
	else
		throw new Error(
			"Usage: npm run routing:hour -- [--stage build|rebuild|qualify|cuts] [--run-name name] [--source-run name]",
		);
}
await runOfflineNoSwap({
	directory: "compact-pilot",
	name:
		options.name ??
		(["build", "qualify"].includes(options.stage)
			? "hour-v3"
			: `hour-v3-${options.stage}`),
	worker: "hour_increment.py",
	memory: "4g",
	args: ["--stage", options.stage, "--source-run", options.source],
	readOnlyMounts: [
		{ source: resolve(root, "data"), target: "/inputs" },
		{
			source: resolve(root, "docs/evidence/hour-preflight-2026-10-17"),
			target: "/admission",
		},
	],
});
