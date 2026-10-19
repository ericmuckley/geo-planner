import { createFileRoute, Link } from "@tanstack/react-router";
import {
	ArrowUpRight,
	Clock3,
	Download,
	Fuel,
	MapPin,
	Mountain,
	Play,
	RotateCcw,
	Save,
	Trees,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ResearchMap } from "../components/research-map";
import {
	defaultQuery,
	type EngineConfig,
	engineConfigSchema,
	type Origin,
	originSchema,
	querySchema,
	type ReachabilityQuery,
	type ReachabilityResult,
	resultSchema,
	type SavedRun,
} from "../lib/reachability";
import { maxSavedRuns, readSavedRuns, writeSavedRuns } from "../lib/saved-runs";
import { cn } from "../lib/utils";

export const Route = createFileRoute("/")({ component: Home });

const fieldClass =
	"w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--lagoon-deep)]";
const buttonClass =
	"inline-flex items-center justify-center gap-2 rounded-lg border border-[var(--line)] px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-45 focus-visible:ring-2 focus-visible:ring-[var(--lagoon-deep)]";

function toDraft(query: ReachabilityQuery) {
	return {
		lat: String(query.origin.lat),
		lon: String(query.origin.lon),
		minutes: String(query.budgetMinutes),
	};
}

function Home() {
	const [draft, setDraft] = useState(toDraft(defaultQuery));
	const [config, setConfig] = useState<EngineConfig | null>(null);
	const [configError, setConfigError] = useState<string | null>(null);
	const [result, setResult] = useState<ReachabilityResult | null>(null);
	const [activeRun, setActiveRun] = useState<SavedRun | null>(null);
	const [savedRuns, setSavedRuns] = useState<SavedRun[]>([]);
	const [historyDirty, setHistoryDirty] = useState(false);
	const [storageError, setStorageError] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [running, setRunning] = useState(false);
	const [showContour, setShowContour] = useState(true);
	const hosted = config?.provider === "openrouteservice";
	const canCompute =
		config?.configured &&
		(config.health === "ready" || config.health === "unchecked");
	const controller = useRef<AbortController | null>(null);
	const sequence = useRef(0);
	const parsed = querySchema.safeParse({
		...defaultQuery,
		origin: {
			lat: draft.lat.trim() ? Number(draft.lat) : NaN,
			lon: draft.lon.trim() ? Number(draft.lon) : NaN,
		},
		budgetMinutes: draft.minutes.trim() ? Number(draft.minutes) : NaN,
	});
	const parsedOrigin = originSchema.safeParse({
		lat: draft.lat.trim() ? Number(draft.lat) : NaN,
		lon: draft.lon.trim() ? Number(draft.lon) : NaN,
	});
	const origin = parsedOrigin.success ? parsedOrigin.data : defaultQuery.origin;

	useEffect(() => {
		const abort = new AbortController();
		fetch("/api/reachability", { signal: abort.signal })
			.then(async (response) => {
				if (!response.ok)
					throw new Error(
						"Could not load routing configuration. Check the app server settings.",
					);
				return engineConfigSchema.parse(await response.json());
			})
			.then(setConfig)
			.catch((cause) => {
				if (!abort.signal.aborted) setConfigError(cause.message);
			});
		try {
			setSavedRuns(readSavedRuns());
		} catch {
			setStorageError(
				"Saved history could not be read. New saves will replace the unreadable history if browser storage is available.",
			);
		}
		return () => {
			abort.abort();
			controller.current?.abort();
		};
	}, []);

	useEffect(() => {
		if (!historyDirty) return;
		try {
			writeSavedRuns(savedRuns);
			setStorageError(null);
		} catch {
			setStorageError(
				"Browser storage is unavailable. Keep this tab open or export your runs to preserve them.",
			);
		}
	}, [savedRuns, historyDirty]);

	const updateDraft = useCallback(
		(patch: Partial<ReturnType<typeof toDraft>>) => {
			sequence.current += 1;
			controller.current?.abort();
			setRunning(false);
			setResult(null);
			setActiveRun(null);
			setError(null);
			setDraft((previous) => ({ ...previous, ...patch }));
		},
		[],
	);
	const selectOrigin = useCallback(
		(selected: Origin) =>
			updateDraft({
				lat: selected.lat.toFixed(6),
				lon: selected.lon.toFixed(6),
			}),
		[updateDraft],
	);
	const onMapIdle = useCallback((id: string, milliseconds: number) => {
		setActiveRun((run) =>
			run?.id === id ? { ...run, sourceToMapIdleMs: milliseconds } : run,
		);
		setSavedRuns((runs) =>
			runs.map((run) =>
				run.id === id ? { ...run, sourceToMapIdleMs: milliseconds } : run,
			),
		);
	}, []);

	function saveRun(run: SavedRun) {
		setSavedRuns((runs) =>
			[run, ...runs.filter((item) => item.id !== run.id)].slice(
				0,
				maxSavedRuns,
			),
		);
		setHistoryDirty(true);
	}

	async function runQuery(query: ReachabilityQuery) {
		controller.current?.abort();
		const abort = new AbortController();
		controller.current = abort;
		const requestNumber = ++sequence.current;
		setDraft(toDraft(query));
		setRunning(true);
		setResult(null);
		setActiveRun(null);
		setError(null);
		const started = performance.now();
		try {
			const response = await fetch("/api/reachability", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(query),
				signal: abort.signal,
			});
			const body = await response.json();
			if (!response.ok)
				throw new Error(
					typeof body.error === "string"
						? body.error
						: "Reachability request failed.",
				);
			const next = resultSchema.parse(body);
			if (sequence.current !== requestNumber) return;
			const run: SavedRun = {
				id: next.id,
				createdAt: next.createdAt,
				query: next.query,
				metadata: next.metadata,
				clientRequestMs: performance.now() - started,
			};
			setResult(next);
			setActiveRun(run);
			if (next.metadata.engine === "openrouteservice") {
				setConfig(
					(previous) =>
						previous && {
							...previous,
							health: "ready",
							checkedAt: next.createdAt,
							healthMessage: "The last hosted contour completed successfully.",
						},
				);
			}
			saveRun(run);
		} catch (cause) {
			if (!abort.signal.aborted && sequence.current === requestNumber) {
				setError(
					cause instanceof Error
						? cause.message
						: "Reachability request failed.",
				);
			}
		} finally {
			if (sequence.current === requestNumber) setRunning(false);
		}
	}

	function exportRuns() {
		const url = URL.createObjectURL(
			new Blob([JSON.stringify({ version: 1, runs: savedRuns }, null, 2)], {
				type: "application/json",
			}),
		);
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = "geo-planner-runs.json";
		anchor.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	return (
		<main className="mx-auto max-w-[1600px] p-4 text-[var(--sea-ink)] md:p-7">
			<header className="mb-6 flex flex-wrap items-end justify-between gap-4">
				<div>
					<p className="island-kicker mb-2">Geo Planner / Research workspace</p>
					<h1 className="display-title text-3xl md:text-4xl">
						How far can you go?
					</h1>
					<p className="mt-2 text-sm text-[var(--sea-ink-soft)]">
						Explore driving reachability, one measured query at a time.
					</p>
					<Link
						to="/experiment"
						className="mt-2 inline-flex text-sm font-semibold underline"
					>
						Try the offline long-range experiment →
					</Link>
				</div>
				<span className="rounded-full border border-[var(--line)] bg-white/70 px-3 py-1.5 text-xs font-semibold">
					{!config && !configError
						? "Checking routing…"
						: config?.health === "unchecked"
							? "Routing key configured"
							: config?.health === "ready"
								? hosted
									? "Routing connected"
									: "Routing ready"
								: config?.configured
									? "Routing unavailable"
									: "Routing not connected"}
				</span>
			</header>
			<div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
				<aside className="space-y-4">
					<section
						className="island-shell rounded-2xl p-5"
						aria-labelledby="query-heading"
					>
						<h2
							id="query-heading"
							className="mb-4 flex items-center gap-2 font-bold"
						>
							<MapPin size={18} /> Define a query
						</h2>
						<form
							onSubmit={(event) => {
								event.preventDefault();
								if (parsed.success) void runQuery(parsed.data);
							}}
						>
							<div className="grid grid-cols-2 gap-3">
								<label
									className="space-y-1 text-xs font-semibold"
									htmlFor="latitude"
								>
									<span>Latitude</span>
									<input
										id="latitude"
										className={fieldClass}
										type="number"
										min={-85}
										max={85}
										step="any"
										required
										value={draft.lat}
										onChange={(event) =>
											updateDraft({ lat: event.target.value })
										}
									/>
								</label>
								<label
									className="space-y-1 text-xs font-semibold"
									htmlFor="longitude"
								>
									<span>Longitude</span>
									<input
										id="longitude"
										className={fieldClass}
										type="number"
										min={-180}
										max={180}
										step="any"
										required
										value={draft.lon}
										onChange={(event) =>
											updateDraft({ lon: event.target.value })
										}
									/>
								</label>
							</div>
							<button
								className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[var(--lagoon-deep)]"
								type="button"
								onClick={() => updateDraft(toDraft(defaultQuery))}
							>
								<RotateCcw size={12} /> Reset to San Diego
							</button>
							<label
								className="mt-5 block space-y-2 text-sm font-semibold"
								htmlFor="minutes"
							>
								<span className="flex items-center gap-2">
									<Clock3 size={16} /> Driving time · minutes
								</span>
								<input
									id="minutes"
									className={fieldClass}
									type="number"
									required
									min={1}
									max={config?.maxMinutes ?? 120}
									step={1}
									value={draft.minutes}
									onChange={(event) =>
										updateDraft({ minutes: event.target.value })
									}
								/>
							</label>
							<p className="mt-2 text-xs leading-relaxed text-[var(--sea-ink-soft)]">
								Outbound ·{" "}
								{hosted
									? "openrouteservice driving-car · provider defaults"
									: "Valhalla auto profile · static speeds"}
								. Configured maximum: {config?.maxMinutes ?? 120} minutes.
							</p>
							<button
								className={cn(
									buttonClass,
									"mt-4 w-full border-transparent bg-[var(--lagoon-deep)] text-white hover:bg-[#246f76]",
								)}
								type="submit"
								disabled={running || !canCompute || !parsed.success}
							>
								<Play size={15} /> {running ? "Computing…" : "Compute contour"}
							</button>
							<div className="mt-2 flex gap-2">
								<button
									type="button"
									className={cn(buttonClass, "flex-1 bg-white/70")}
									disabled={!parsed.success}
									onClick={() => {
										if (parsed.success)
											saveRun({
												id: crypto.randomUUID(),
												createdAt: new Date().toISOString(),
												query: parsed.data,
											});
									}}
								>
									<Save size={14} /> Save query
								</button>
								{running && (
									<button
										type="button"
										className={buttonClass}
										onClick={() => {
											sequence.current += 1;
											controller.current?.abort();
											setRunning(false);
										}}
									>
										Cancel
									</button>
								)}
							</div>
						</form>
						<output className="mt-4 block text-xs leading-relaxed">
							{configError ? (
								<p className="text-amber-900">{configError}</p>
							) : !config ? (
								<p>Checking routing configuration…</p>
							) : !config.configured ? (
								<p>
									Routing service not configured. You can explore the map and
									save queries now.{" "}
									{hosted
										? "Set the server-only ORS_API_KEY to compute US driving contours."
										: "Connect a regional Valhalla service to compute contours."}
								</p>
							) : !canCompute ? (
								<p className="text-amber-900">{config.healthMessage}</p>
							) : (
								<div>
									{config.healthMessage && <p>{config.healthMessage}</p>}
									<p>
										Coverage: {config.coverage}. Completeness has not been
										verified.
									</p>
								</div>
							)}
						</output>
					</section>
					<section
						className="island-shell rounded-2xl p-5"
						aria-labelledby="layers-heading"
					>
						<h2 id="layers-heading" className="mb-3 font-bold">
							Analytical layers
						</h2>
						<label className="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								checked={showContour}
								onChange={(event) => setShowContour(event.target.checked)}
								className="accent-[var(--lagoon-deep)]"
							/>{" "}
							Reachability contour
						</label>
						<ul className="mt-4 space-y-3 text-sm text-[var(--sea-ink-soft)]">
							{[
								{
									icon: Fuel,
									label: "Gas stations",
									detail: "Awaiting OSM import",
								},
								{
									icon: Trees,
									label: "Public-land overlap",
									detail: "Awaiting PAD-US import",
								},
								{
									icon: Mountain,
									label: "Elevation >5,000 ft",
									detail: "Awaiting numerical DEM mask",
								},
							].map(({ icon: Icon, label, detail }) => (
								<li key={label} className="flex items-start gap-2">
									<Icon size={16} className="mt-0.5 shrink-0" />
									<div>
										{label}
										<p className="text-xs">{detail}</p>
									</div>
								</li>
							))}
						</ul>
					</section>
				</aside>
				<div className="grid min-w-0 gap-4 lg:grid-rows-[minmax(440px,1fr)_auto]">
					<ResearchMap
						origin={origin}
						result={result}
						showContour={showContour}
						onOriginChange={selectOrigin}
						onMapIdle={onMapIdle}
					/>
					<section
						className="island-shell rounded-2xl p-5"
						aria-labelledby="timing-heading"
					>
						<div className="flex flex-wrap items-center justify-between gap-2">
							<h2 id="timing-heading" className="font-bold">
								Run measurements
							</h2>
							<span className="text-xs text-[var(--sea-ink-soft)]">
								{result
									? `${result.query.budgetMinutes} min · ${new Date(result.createdAt).toLocaleTimeString()}`
									: "No completed run"}
							</span>
						</div>
						{error && (
							<p
								role="alert"
								className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-950"
							>
								{error}
							</p>
						)}
						<dl className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
							{[
								{
									label: "Engine round trip",
									value: result?.metadata.timings.engineRoundTripMs,
								},
								{
									label: "Decode & validate",
									value: result?.metadata.timings.decodeValidateMs,
								},
								{ label: "Browser request", value: activeRun?.clientRequestMs },
								{
									label: "Source → map idle",
									value: activeRun?.sourceToMapIdleMs,
								},
							].map(({ label, value }) => (
								<div key={label}>
									<dt className="text-xs text-[var(--sea-ink-soft)]">
										{label}
									</dt>
									<dd className="mt-1 font-mono text-lg">
										{value === undefined ? "—" : `${value.toFixed(1)} ms`}
									</dd>
								</div>
							))}
						</dl>
						<p className="mt-4 text-xs leading-relaxed text-[var(--sea-ink-soft)]">
							Engine round trip includes HTTP, graph work, and contouring. Map
							idle includes source processing and outstanding map resources; it
							is not a first-paint measurement.
						</p>
						{result && (
							<div className="mt-3 border-t border-[var(--line)] pt-3 text-xs leading-relaxed">
								<p>
									Graph: {result.metadata.graphVersion} · Engine:{" "}
									{result.metadata.engineVersion} · Upstream GeoJSON:{" "}
									{(result.metadata.upstreamBytes / 1024).toFixed(1)} KiB
								</p>
								<p>
									Coverage: {result.metadata.coverage} · Completeness unverified
								</p>
								{result.metadata.engine === "valhalla" ? (
									<p>
										Contour simplification: {result.metadata.generalizeMeters} m
										· Denoise: {result.metadata.denoise}
									</p>
								) : (
									<>
										<p>
											Profile: {result.metadata.profile} · Smoothing:{" "}
											{result.metadata.smoothing}. Snapped origin not
											independently reported.
										</p>
										<p>
											©{" "}
											<a
												className="underline"
												href="https://openrouteservice.org/"
											>
												openrouteservice by HeiGIT
											</a>{" "}
											| Data from{" "}
											<a
												className="underline"
												href="https://www.openstreetmap.org/copyright"
											>
												OpenStreetMap
											</a>{" "}
											· Results{" "}
											<a
												className="underline"
												href="https://creativecommons.org/licenses/by-sa/4.0/"
											>
												CC-BY-SA 4.0
											</a>
										</p>
									</>
								)}
								{result.contours.warnings?.map((warning) => (
									<p
										key={`${warning.code}-${warning.description}`}
										className="mt-1 text-amber-900"
									>
										Engine warning: {warning.description}
									</p>
								))}
							</div>
						)}
					</section>
				</div>
			</div>
			<section
				className="island-shell mt-5 rounded-2xl p-5"
				aria-labelledby="history-heading"
			>
				<div className="flex flex-wrap items-center justify-between gap-3">
					<div>
						<h2 id="history-heading" className="font-bold">
							Saved queries & runs
						</h2>
						<p className="mt-1 text-xs text-[var(--sea-ink-soft)]">
							Last {maxSavedRuns} in this browser. Successful runs save
							automatically. Replay computes a new result with the current
							engine.
						</p>
					</div>
					<button
						className={buttonClass}
						type="button"
						onClick={exportRuns}
						disabled={!savedRuns.length}
					>
						<Download size={14} /> Export JSON
					</button>
				</div>
				{storageError && (
					<output className="mt-3 block text-sm text-amber-900">
						{storageError}
					</output>
				)}
				{!savedRuns.length ? (
					<p className="mt-5 text-sm text-[var(--sea-ink-soft)]">
						Save your first query to make it replayable.
					</p>
				) : (
					<ul className="mt-4 divide-y divide-[var(--line)]">
						{savedRuns.map((run) => (
							<li
								key={run.id}
								className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"
							>
								<div>
									<p className="font-semibold">
										{run.query.budgetMinutes} min from{" "}
										{run.query.origin.lat.toFixed(4)},{" "}
										{run.query.origin.lon.toFixed(4)}
									</p>
									<p className="mt-1 text-xs text-[var(--sea-ink-soft)]">
										{new Date(run.createdAt).toLocaleString()} ·{" "}
										{run.metadata
											? `Graph ${run.metadata.graphVersion} · ${run.clientRequestMs?.toFixed(1) ?? "—"} ms browser request`
											: "Query only"}
									</p>
								</div>
								<div className="flex gap-2">
									<button
										className={buttonClass}
										type="button"
										onClick={() => updateDraft(toDraft(run.query))}
									>
										Load
									</button>
									<button
										className={buttonClass}
										type="button"
										disabled={running || !canCompute}
										onClick={() => void runQuery(run.query)}
									>
										<ArrowUpRight size={14} /> Replay
									</button>
								</div>
							</li>
						))}
					</ul>
				)}
			</section>
			<footer className="mt-5 max-w-4xl text-xs leading-relaxed text-[var(--sea-ink-soft)]">
				This is a research baseline. Filled contours approximate road-network
				reachability and do not establish access to every shaded point.
				Road-distance and combined-budget semantics, verified coverage, spatial
				layers, and shared PostgreSQL run storage are upcoming work.
			</footer>
		</main>
	);
}
