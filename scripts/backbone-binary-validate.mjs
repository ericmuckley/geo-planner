import assert from "node:assert/strict";

const names = [
	"nodeCoordinates",
	"arcFrom",
	"arcTo",
	"arcRoadKm",
	"arcMinutes",
	"arcSpeedKph",
	"arcByteOffsets",
	"arcInteriorOffsets",
	"interiorSourceKm",
	"geometryBytes",
	"partArcOffsets",
	"endpointAdjOffsets",
	"endpointAdjArcs",
	"crossingFirstArc",
	"cellIds",
	"cellArcOffsets",
	"cellArcs",
];

// The source geometry stream seeds deltas with Python's ties-to-even rounding.
export function roundEven(value) {
	const lower = Math.floor(value);
	const fraction = value - lower;
	return fraction === 0.5
		? lower % 2 === 0
			? lower
			: lower + 1
		: fraction < 0.5
			? lower
			: lower + 1;
}

function offsets(values, count, end) {
	assert.equal(values.length, count + 1);
	assert.equal(values[0], 0);
	assert.equal(values[count], end);
	for (let i = 1; i <= count; i++)
		assert.ok(values[i] >= values[i - 1] && values[i] <= end);
}

export function validateBackbone(data, stats, kept) {
	assert.deepEqual(Object.keys(data).sort(), [...names].sort());
	const n = data.nodeCoordinates.length / 2;
	const m = data.arcFrom.length;
	const original = stats.originalNodes;
	assert.ok(Number.isInteger(n) && n === stats.nodes && m === stats.arcs);
	assert.ok(Number.isInteger(original) && original > 0 && original <= n);
	assert.ok(Number.isInteger(kept.width) && Number.isInteger(kept.height));
	const [west, south, east, north] = kept.bounds;
	for (let i = 0; i < n; i++) {
		const x = data.nodeCoordinates[i * 2],
			y = data.nodeCoordinates[i * 2 + 1];
		assert.ok(Number.isFinite(x) && x >= west && x <= east);
		assert.ok(Number.isFinite(y) && y >= south && y <= north);
	}
	for (const name of ["arcTo", "arcRoadKm", "arcMinutes", "arcSpeedKph"])
		assert.equal(data[name].length, m);
	offsets(data.arcByteOffsets, m, data.geometryBytes.length);
	offsets(data.arcInteriorOffsets, m, data.interiorSourceKm.length);
	offsets(data.partArcOffsets, stats.parts, m);
	const speeds = new Set(Object.values(kept.censusRoadSpeedsKph));
	for (let arc = 0; arc < m; arc++) {
		const a = data.arcFrom[arc],
			b = data.arcTo[arc],
			km = data.arcRoadKm[arc];
		assert.ok(a < n && b < n && Number.isFinite(km) && km > 0);
		assert.ok(
			Number.isFinite(data.arcMinutes[arc]) && data.arcMinutes[arc] > 0,
		);
		assert.ok(speeds.has(data.arcSpeedKph[arc]));
		const first = data.arcInteriorOffsets[arc],
			last = data.arcInteriorOffsets[arc + 1];
		let previous = 0;
		for (let i = first; i < last; i++) {
			const value = data.interiorSourceKm[i];
			assert.ok(
				Number.isFinite(value) && value >= previous && value <= km + 1e-9,
			);
			previous = value;
		}
		let x = roundEven(data.nodeCoordinates[a * 2] * 100000);
		let y = roundEven(data.nodeCoordinates[a * 2 + 1] * 100000);
		let value = 0,
			shift = 0,
			count = 0;
		for (
			let i = data.arcByteOffsets[arc];
			i < data.arcByteOffsets[arc + 1];
			i++
		) {
			const byte = data.geometryBytes[i];
			assert.ok(shift < 28 || byte <= 15);
			value += (byte & 127) * 2 ** shift;
			if (byte & 128) {
				shift += 7;
				continue;
			}
			assert.ok(shift === 0 || byte !== 0);
			const signed = (value >>> 1) ^ -(value & 1);
			if (count % 2 === 0) x += signed;
			else {
				y += signed;
				assert.ok(x / 100000 >= west && x / 100000 <= east);
				assert.ok(y / 100000 >= south && y / 100000 <= north);
			}
			count++;
			value = 0;
			shift = 0;
		}
		assert.equal(shift, 0);
		assert.equal(count, 2 * (last - first));
	}
	offsets(data.endpointAdjOffsets, original, data.endpointAdjArcs.length);
	for (let node = 0; node < original; node++) {
		for (
			let i = data.endpointAdjOffsets[node];
			i < data.endpointAdjOffsets[node + 1];
			i++
		) {
			const arc = data.endpointAdjArcs[i];
			assert.ok(
				arc < m && (data.arcFrom[arc] === node || data.arcTo[arc] === node),
			);
		}
	}
	assert.equal(data.crossingFirstArc.length, n - original);
	for (let i = 0; i < data.crossingFirstArc.length; i++) {
		const arc = data.crossingFirstArc[i],
			node = original + i;
		assert.ok(
			arc + 1 < m && data.arcTo[arc] === node && data.arcFrom[arc + 1] === node,
		);
	}
	offsets(data.cellArcOffsets, data.cellIds.length, data.cellArcs.length);
	for (let i = 0; i < data.cellIds.length; i++) {
		assert.ok(
			data.cellIds[i] < kept.width * kept.height &&
				(i === 0 || data.cellIds[i] > data.cellIds[i - 1]),
		);
		for (let j = data.cellArcOffsets[i]; j < data.cellArcOffsets[i + 1]; j++)
			assert.ok(
				data.cellArcs[j] < m &&
					(j === data.cellArcOffsets[i] ||
						data.cellArcs[j] > data.cellArcs[j - 1]),
			);
	}
	return {
		nodes: n,
		arcs: m,
		originalNodes: original,
		graphArrays: names.length,
		interiorVertices: data.interiorSourceKm.length,
		indexedCells: data.cellIds.length,
		allFormatAndIndexChecks: true,
	};
}
