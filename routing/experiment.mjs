import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { root } from "./settings.mjs";

const options = { graph: "two-hour-region-v2", cuts: null };
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (!/^[a-zA-Z0-9_-]+$/.test(value ?? ""))
		throw new Error(
			"Graph names accept letters, numbers, underscores and hyphens",
		);
	if (option === "--graph-run") options.graph = value;
	else if (option === "--cuts-run") options.cuts = value;
	else
		throw new Error(
			"Usage: npm run dev:experiment -- [--graph-run name] [--cuts-run name]",
		);
}
options.cuts ??= `${options.graph}-cuts`;
let expectedIdentity;
let worker;
let app;
let stopped = false;
function stop() {
	if (stopped) return;
	stopped = true;
	app?.kill("SIGTERM");
	worker?.kill("SIGINT");
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);

async function ready() {
	let response;
	try {
		response = await fetch("http://127.0.0.1:8787/health", {
			signal: AbortSignal.timeout(1500),
		});
	} catch {
		return false;
	}
	if (!response.ok) throw new Error("Port 8787 is used by another service");
	const config = await response.json();
	if (!config.ready || config.graphIdentity !== expectedIdentity)
		throw new Error(
			`Port 8787 has a different routing graph. Stop that worker, then restart for ${options.graph}.`,
		);
	return true;
}

try {
	expectedIdentity = JSON.parse(
		await readFile(
			resolve(root, "data/compact-pilot", options.graph, "manifest.json"),
			"utf8",
		),
	).graphIdentity;
	if (!(await ready())) {
		worker = spawn(
			"python3",
			[
				"-B",
				resolve(root, "routing/experiment.py"),
				"--graph-run",
				options.graph,
				"--cuts-run",
				options.cuts,
			],
			{
				cwd: root,
				stdio: "inherit",
			},
		);
		worker.on("error", (error) => {
			console.error(error.message);
			stop();
		});
		worker.on("exit", (code) => {
			if (!stopped) {
				process.exitCode = code || 1;
				stop();
			}
		});
	}
	const deadline = Date.now() + 180000;
	while (!stopped && !(await ready())) {
		if (Date.now() > deadline)
			throw new Error("Local router did not become ready within three minutes");
		await delay(500);
	}
	if (!stopped) {
		console.log(
			"Open /experiment on the Vite URL below. Hosted environment values are preserved.",
		);
		app = spawn("npm", ["run", "dev", "--", "--host", "127.0.0.1"], {
			cwd: root,
			stdio: "inherit",
			env: { ...process.env, LOCAL_ROUTING_EXPERIMENT: "1" },
		});
		app.on("error", (error) => {
			console.error(error.message);
			stop();
		});
		app.on("exit", (code) => {
			process.exitCode = code ?? 1;
			stop();
		});
	}
} catch (error) {
	console.error(error instanceof Error ? error.message : error);
	process.exitCode = 1;
	stop();
}
