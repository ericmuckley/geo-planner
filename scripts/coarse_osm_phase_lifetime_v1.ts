/** Host verifier phase boundary; never imported by the application runtime. */
import assert from "node:assert/strict";
import { setImmediate } from "node:timers/promises";

export async function settledPhaseMemory() {
	const collect = global.gc;
	assert.ok(collect, "Host lifetime checks require --expose-gc");
	collect();
	await setImmediate();
	collect();
	return process.memoryUsage();
}

export async function assertPhaseReleased(
	baselineArrayBuffers: number,
	scope: string,
) {
	const memory = await settledPhaseMemory();
	assert.ok(
		memory.arrayBuffers <= baselineArrayBuffers + 1048576,
		`${scope}: retained backing buffers; baseline=${baselineArrayBuffers}, observed=${memory.arrayBuffers}`,
	);
	return memory;
}
