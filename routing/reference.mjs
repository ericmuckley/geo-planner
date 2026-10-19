import { readFile } from "node:fs/promises";
import { runOffline } from "./offline.mjs";
import { manifest } from "./settings.mjs";

const profile = JSON.parse(
	await readFile(
		new URL("./profiles/reference-downtown-v1.json", import.meta.url),
		"utf8",
	),
);
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error("Usage: npm run routing:reference -- [--run-name name]");
await runOffline({
	directory: "reference-pilot",
	name: args[1] ?? profile.id,
	worker: "reference.py",
	memory: "4g",
	args: ["--expected-graph", manifest.id],
});
