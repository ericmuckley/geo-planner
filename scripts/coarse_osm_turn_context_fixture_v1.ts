/** Small synthetic metadata encoder for independent context-search controls. */
import type { TurnContextFiles } from "./coarse_osm_turn_contexts_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

export type ContextArc = { tail: number; head: number; way: number };
export type ContextRule = readonly [number, number, number];

export function contextFiles(
	arcs: ContextArc[],
	rules: ContextRule[],
): TurnContextFiles {
	const groups = new Map<
		string,
		{ from: number; via: number; to: Set<number> }
	>();
	for (const [from, via, to] of rules) {
		const key = `${from}/${via}`;
		let group = groups.get(key);
		if (!group) {
			group = { from, via, to: new Set() };
			groups.set(key, group);
		}
		group.to.add(to);
	}
	const ordered = [...groups.values()].sort(
		(a, b) => a.from - b.from || a.via - b.via,
	);
	const stateOffsets = [0],
		states: number[] = [],
		exitOffsets = [0],
		exits: number[] = [],
		triggers: number[][] = [];
	for (const group of ordered) {
		const via = arcs.flatMap((a, i) => (a.way === group.via ? [i] : []));
		const heads = new Set(via.map((i) => arcs[i].head));
		const start = states.length;
		states.push(...via);
		stateOffsets.push(states.length);
		exits.push(
			...arcs.flatMap((a, i) =>
				group.to.has(a.way) && heads.has(a.tail) ? [i] : [],
			),
		);
		exitOffsets.push(exits.length);
		arcs.forEach((before, i) => {
			if (before.way !== group.from) return;
			via.forEach((after, index) => {
				if (before.head === arcs[after].tail)
					triggers.push([i, after, start + index]);
			});
		});
	}
	triggers.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
	const incoming = new Uint8Array(Math.ceil(arcs.length / 8));
	for (const [before] of triggers) incoming[before >> 3] |= 1 << (before & 7);
	const u32 = (values: number[]) =>
		new Uint8Array(Uint32Array.from(values).buffer);
	return {
		"context/state-offsets.u32": u32(stateOffsets),
		"context/state-arcs.u24": packUint24(states),
		"context/exit-offsets.u32": u32(exitOffsets),
		"context/exit-arcs.u24": packUint24(exits),
		"context/triggers.u24": packUint24(triggers.flat()),
		"context/trigger-incoming.bit": incoming,
	};
}
