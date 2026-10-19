import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { root } from "./settings.mjs";

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
	try {
		const response = await fetch("http://127.0.0.1:8787/health", {
			signal: AbortSignal.timeout(1500),
		});
		if (!response.ok || !(await response.json()).ready)
			throw new Error("Port 8787 is used by another service");
		return true;
	} catch (error) {
		if (error instanceof Error && error.message.includes("another service"))
			throw error;
		return false;
	}
}

try {
	if (!(await ready())) {
		worker = spawn("python3", ["-B", resolve(root, "routing/experiment.py")], {
			cwd: root,
			stdio: "inherit",
		});
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
