import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";
import { decodeContainer } from "./backbone-binary-format.mjs";
import { validateBackbone } from "./backbone-binary-validate.mjs";

export function loadBackboneBinary(url, expected, decodeGrid) {
	const started = performance.now();
	assert.equal(url.protocol, "file:");
	assert.equal(statSync(url).size, expected.bytes);
	assert.ok(expected.bytes <= 80_000_000);
	const { graph, kept, stats, parity } = decodeContainer(
		readFileSync(url),
		expected.sha256,
	);
	assert.equal(parity.graphArrays, 17);
	assert.equal(parity.keptBlobs, 12);
	const validation = validateBackbone(graph, stats, kept);
	// Use the existing complete decoder/validation for the retained coarse base.
	// The temporary encoded JSON/container is not retained by the returned state.
	const base = decodeGrid(kept);
	assert.ok(!base.roadLayer && !base.supplementalRoadVisits);
	const loadDecodeValidateMs = performance.now() - started;
	return {
		graph,
		base,
		summary: {
			...parity,
			...validation,
			loadDecodeValidateMs,
			baseLandCells: base.width * base.height,
			baseRoadVisits: base.roadVisits?.size ?? 0,
			probeOnly: true,
			routingAvailable: false,
			scope:
				"Local file load, exact parity and format/index/base validation; no search, contour or cloud cold-start claim.",
		},
	};
}
