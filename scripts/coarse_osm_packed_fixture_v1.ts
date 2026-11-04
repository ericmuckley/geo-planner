import assert from "node:assert/strict";
import type { PackedCarFiles } from "./coarse_osm_packed_car_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

export type TestArc = [
	tail: number,
	head: number,
	ticks: number,
	reverse?: number,
];

export function words(
	values: number[],
	width: 2 | 4,
	signed = false,
): Uint8Array {
	const bytes = new Uint8Array(width * values.length);
	const view = new DataView(bytes.buffer);
	values.forEach((value, i) => {
		if (width === 2) view.setUint16(2 * i, value, true);
		else if (signed) view.setInt32(4 * i, value, true);
		else view.setUint32(4 * i, value, true);
	});
	return bytes;
}

export function fixture(
	vertices: number,
	arcs: TestArc[],
	flags: number[] = Array(vertices).fill(4),
	pairs: number[] = [],
): PackedCarFiles {
	assert.ok(arcs.every((row, i) => !i || row[0] >= arcs[i - 1][0]));
	const offsets = Array(vertices + 1).fill(0);
	for (const [tail] of arcs) offsets[tail + 1]++;
	for (let i = 0; i < vertices; i++) offsets[i + 1] += offsets[i];
	const costKeys: number[] = [];
	const costValues: number[] = [];
	const reverseKeys: number[] = [];
	const reverseValues: number[] = [];
	const reverse = arcs.map(([, head, cost, other], arc) => {
		if (cost >= 65535) {
			costKeys.push(arc);
			costValues.push(cost);
		}
		if (other === undefined) return 255;
		const ordinal = other - offsets[head];
		if (ordinal < 254) return ordinal;
		reverseKeys.push(arc);
		reverseValues.push(other);
		return 254;
	});
	return {
		"routing/xy.i32": words(Array(vertices * 2).fill(0), 4, true),
		"routing/offsets.u24": packUint24(offsets),
		"routing/targets.u24": packUint24(arcs.map((row) => row[1])),
		"routing/costs.u16": words(
			arcs.map((row) => Math.min(row[2], 65535)),
			2,
		),
		"routing/cost-overflow-arcs.u24": packUint24(costKeys),
		"routing/cost-overflow-ticks.u32": words(costValues, 4),
		"routing/reverse.u8": Uint8Array.from(reverse),
		"routing/reverse-overflow-arcs.u24": packUint24(reverseKeys),
		"routing/reverse-overflow-targets.u24": packUint24(reverseValues),
		"routing/node-flags.u8": Uint8Array.from(flags),
		"routing/forbidden-turns.u24": packUint24(pairs),
	};
}
