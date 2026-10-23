// Reproduce local retained-memory observations; run from the repository root.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { decodeGrid } from "../../../src/server/coarse-data.server.ts";

const artifact = process.argv[2];
if (!artifact || !global.gc) throw new Error("Pass an artifact and --expose-gc");
const raw = readFileSync(artifact);
const data = JSON.parse(raw);
global.gc();
const before = process.memoryUsage();
const start = performance.now();
const grid = decodeGrid(data);
const decodeMs = performance.now() - start;
global.gc();
const after = process.memoryUsage();
console.log(JSON.stringify({
  artifact,
  sha256: createHash("sha256").update(raw).digest("hex"),
  visits: grid.roadVisits.size,
  supplementalVisits: grid.supplementalRoadVisits?.size ?? 0,
  decodeMs, before, after,
  retainedHeapDeltaBytes: after.heapUsed - before.heapUsed,
  processMaxRssKiB: process.resourceUsage().maxRSS,
  scope: "Fresh local Node process with encoded input already parsed, explicit GC before/after decode. Heap delta is decoded retained objects; peak RSS is whole process lifetime including tool/input parse. Not Vercel memory, isolated decoder peak or national forecast.",
}, null, 2));
