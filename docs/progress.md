# Where Geo Planner stands

Updated October 23, 2026. **V8 is active locally with finer 0.025° contours. V7/v8 changes are uncommitted; v6 at `ffd7fec` is user-reported verified live.**

- **Smaller computed cells:** about 1.8–2.8 km, half v7's width. All geometry is rebuilt from the pinned national sources; v7's generic paid Census road-state rule remains. No named-location routing exceptions. [Comparison maps](evidence/coarse-finer-2026-10-23/README.md).
- **Measured improvement:** 29 of 35 saved trips improve, six worsen, at most +3.18 min. Mean absolute reference differences fall 11.58→10.29 / 17.21→12.01 min; every destination is reached/shaded. These reused regional references do not establish national or long-horizon accuracy.
- **Deployment stays simple:** lossless compression reduces the finer 179.92 MB model to 61.21 MB; the checked local Vercel function is 65.02 MB. Three fresh first computations take 3.59–3.66s after config, zero routing fetches. No new dependency, env variable or DB migration.
- **Bounded storage:** decoded retained heap+buffers is 158.04 MB, with stable query retention over 952,758 inputs. Encoded input, transient/peak memory and cloud capacity are separate and unmeasured.
- **Checked:** 56 server tests, nineteen Python fixtures, full link/shore/transfer proofs, independent source/packed repeats, 42 active API cases, check/typechecks, both builds and local handler pass. Browser review covers twelve paired maps and main-app 6/10/12h plus fixture cloud reload/replay.
- **Remaining limits:** merged crossings, one road position per layer, source gaps, assumed overland travel and traffic/turn/terrain/access/ferry/border omissions. Cell size is not an accuracy bound. [Model](coarse-estimator.md).
- **Next:** publish/verify latest v8, then plan independent nonregional 6–12h validation before further fitting or resolution increases. New references require explicit quota authorization. [Next steps](next-steps.md).

A fresh clone still contains v6. Include both `src/server/data/coarse-grid-v7.json` and `coarse-grid-v8.json` with the accumulated code/tools/tests/evidence/docs when publishing. Preserve all older/failed evidence, ignored source assets and credentials. Cloud history remains twenty summaries per private browser owner with local fallback. [Resume guide](agent-handoff.md).
