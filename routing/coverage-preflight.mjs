import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
let name = "san-diego-tijuana-buffer-preflight-v1";
if (args.length) {
	if (args.length !== 2 || args[0] !== "--run-name" || !args[1])
		throw new Error("Usage: npm run routing:coverage -- [--run-name name]");
	name = args[1];
}
await runOffline({
	directory: "coverage-pilot",
	name,
	worker: "coverage_preflight.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [
		["barrier-pilot/san-diego-tijuana-wide-v3", "/calibration"],
		["regional-pilot/san-diego-tijuana-v2", "/calibration-source"],
	].map(([path, target]) => ({ source: resolve(root, "data", path), target })),
});
