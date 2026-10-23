import { createFileRoute, Link } from "@tanstack/react-router";
import {
	ArrowUpRight,
	Clock3,
	CloudUpload,
	Download,
	Fuel,
	LoaderCircle,
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
import {
	getRunModel,
	maxSavedRuns,
	mergeSavedRuns,
	readSavedRuns,
	writeSavedRuns,
} from "../lib/saved-runs";
import { useCloudHistory } from "../lib/use-cloud-history";
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

function formatDuration(minutes: number) {
	const hours = Math.floor(minutes / 60);
	const remainder = minutes % 60;
	return [
		hours ? `${hours} ${hours === 1 ? "hour" : "hours"}` : "",
		remainder ? `${remainder} min` : "",
	]
		.filter(Boolean)
		.join(" ");
}

function Home() {
	const [model, setModel] = useState<"coarse" | "connected">("coarse");
	const [draft, setDraft] = useState(
		toDraft({ ...defaultQuery, budgetMinutes: 120 }),
	);
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
	const loadCloudRuns = useCallback((runs: SavedRun[]) => {
		setSavedRuns((current) => mergeSavedRuns(current, runs));
		setHistoryDirty(true);
	}, []);
	const cloudHistory = useCloudHistory(loadCloudRuns);
	const hosted = config?.provider === "openrouteservice";
	const coarse = model === "coarse";
	const endpoint = coarse ? "/api/estimate" : "/api/reachability";
	const canCompute =
		config?.configured &&
		(config.health === "ready" || config.health === "unchecked");
	const controller = useRef<AbortController | null>(null);
	const sequence = useRef(0);
	const pendingMinutes = useRef<string | null>(null);
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
	const minMinutes = config?.minMinutes ?? (coarse ? 30 : 1);
	const maxMinutes = config?.maxMinutes ?? (coarse ? 720 : 60);
	const withinLimits =
		parsed.success &&
		parsed.data.budgetMinutes >= minMinutes &&
		parsed.data.budgetMinutes <= maxMinutes;

	useEffect(() => {
		const abort = new AbortController();
		setConfigError(null);
		fetch(endpoint, { signal: abort.signal })
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
		return () => abort.abort();
	}, [endpoint]);

	useEffect(() => {
		try {
			setSavedRuns(readSavedRuns());
		} catch {
			setStorageError(
				"Saved history could not be read. New saves will replace the unreadable history if browser storage is available.",
			);
		}
		return () => {
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
			pendingMinutes.current = null;
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
		setSavedRuns((runs) => mergeSavedRuns([run], runs));
		setHistoryDirty(true);
		cloudHistory.save(run);
	}

	function commitDrivingTime() {
		const value = pendingMinutes.current;
		pendingMinutes.current = null;
		if (value === null || !canCompute) return;
		if (!parsedOrigin.success) {
			setError("Enter valid coordinates before estimating an area.");
			return;
		}
		const budgetMinutes = Number(value);
		if (budgetMinutes < minMinutes || budgetMinutes > maxMinutes) return;
		void runQuery({
			...defaultQuery,
			origin: parsedOrigin.data,
			budgetMinutes,
		});
	}

	async function runQuery(query: ReachabilityQuery, selectedModel = model) {
		if (selectedModel !== model) {
			setConfig(null);
			setModel(selectedModel);
		}
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
			const response = await fetch(
				selectedModel === "coarse" ? "/api/estimate" : "/api/reachability",
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(query),
					signal: abort.signal,
				},
			);
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
				model: selectedModel,
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
					<p className="island-kicker mb-2">
						Geo Planner / Long-range estimates
					</p>
					<h1 className="display-title text-3xl md:text-4xl">
						How far can you go?
					</h1>
					<p className="mt-2 text-sm text-[var(--sea-ink-soft)]">
						Explore approximate driving areas across the contiguous US, up to 12
						hours away.
					</p>
					<Link
						to="/experiment"
						className="mt-2 inline-flex text-sm font-semibold underline"
					>
						Detailed regional research →
					</Link>
				</div>
				<span className="rounded-full border border-[var(--line)] bg-white/70 px-3 py-1.5 text-xs font-semibold">
					{!config && !configError
						? "Checking routing…"
						: config?.health === "unchecked"
							? "Routing key configured"
							: config?.health === "ready"
								? coarse
									? "Nationwide estimate ready"
									: hosted
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
						<label
							className="mb-4 block space-y-2 text-sm font-semibold"
							htmlFor="model"
						>
							<span>Estimate model</span>
							<select
								id="model"
								className={fieldClass}
								value={model}
								onChange={(event) => {
									const next =
										event.target.value === "coarse" ? "coarse" : "connected";
									updateDraft({ minutes: next === "coarse" ? "120" : "60" });
									setConfig(null);
									setModel(next);
								}}
							>
								<option value="coarse">Nationwide · coarse estimate</option>
								<option value="connected">Connected routing provider</option>
							</select>
						</label>
						{coarse && (
							<p className="mb-4 text-xs leading-relaxed text-[var(--sea-ink-soft)]">
								Road-informed grid, about 1.8–2.8 km per cell. Local access is
								estimated; accuracy has not been calibrated. No routing API key
								needed.
							</p>
						)}
						<form
							onSubmit={(event) => {
								event.preventDefault();
								if (parsed.success && withinLimits) void runQuery(parsed.data);
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
								onClick={() =>
									updateDraft(
										toDraft({
											...defaultQuery,
											budgetMinutes: coarse ? 120 : 60,
										}),
									)
								}
							>
								<RotateCcw size={12} /> Reset to San Diego
							</button>
							<label
								className="mt-5 block space-y-2 text-sm font-semibold"
								htmlFor="minutes"
							>
								<span className="flex items-center justify-between gap-2">
									<span className="flex items-center gap-2">
										<Clock3 size={16} /> Driving time
									</span>
									<span
										id="driving-time-value"
										className="tabular-nums text-[var(--lagoon-deep)]"
									>
										{formatDuration(Number(draft.minutes))}
									</span>
								</span>
								<input
									id="minutes"
									className="h-7 w-full cursor-pointer accent-[var(--lagoon-deep)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--lagoon-deep)] disabled:cursor-wait disabled:opacity-50"
									type="range"
									aria-label="Driving time"
									aria-valuetext={formatDuration(Number(draft.minutes))}
									aria-describedby="driving-time-hint"
									min={minMinutes}
									max={maxMinutes}
									step={1}
									value={draft.minutes}
									disabled={!config}
									onChange={(event) => {
										const minutes = event.currentTarget.value;
										pendingMinutes.current = minutes;
										setDraft((previous) => ({ ...previous, minutes }));
									}}
									onPointerDown={(event) =>
										event.currentTarget.setPointerCapture(event.pointerId)
									}
									onPointerUp={commitDrivingTime}
									onKeyUp={commitDrivingTime}
									onBlur={commitDrivingTime}
									onPointerCancel={() => {
										pendingMinutes.current = null;
									}}
								/>
								<span className="flex justify-between text-xs font-normal text-[var(--sea-ink-soft)]">
									<span>{formatDuration(minMinutes)}</span>
									<span>{formatDuration(maxMinutes)}</span>
								</span>
							</label>
							<output
								id="driving-time-hint"
								className="mt-1 block text-xs text-[var(--sea-ink-soft)]"
							>
								{running ? "Updating area…" : "Release to update the map."}
							</output>
							<p className="mt-2 text-xs leading-relaxed text-[var(--sea-ink-soft)]">
								Outbound ·{" "}
								{coarse
									? "coarse major-road and local travel estimate"
									: hosted
										? "openrouteservice driving-car · provider defaults"
										: "Valhalla auto profile · static speeds"}
								. Maximum: {formatDuration(maxMinutes)}.
							</p>
							<button
								className={cn(
									buttonClass,
									"mt-4 w-full border-transparent bg-[var(--lagoon-deep)] text-white hover:bg-[#246f76]",
								)}
								type="submit"
								disabled={running || !canCompute || !withinLimits}
							>
								<Play size={15} />{" "}
								{running
									? "Computing…"
									: coarse
										? "Estimate area"
										: "Compute contour"}
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
												model,
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
										Coverage: {config.coverage}.{" "}
										{coarse
											? "Approximate planning model."
											: "Completeness has not been verified."}
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
					<div className="relative min-h-[440px]" aria-busy={running}>
						<ResearchMap
							origin={origin}
							result={result}
							showContour={showContour}
							onOriginChange={selectOrigin}
							onMapIdle={onMapIdle}
						/>
						{running && (
							<div
								aria-hidden="true"
								className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl bg-white/70"
							>
								<span className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold shadow-sm">
									<LoaderCircle className="animate-spin" size={18} /> Updating
									area…
								</span>
							</div>
						)}
					</div>
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
									label:
										result?.metadata.engine === "coarse"
											? "Grid search"
											: "Engine round trip",
									value:
										result?.metadata.timings.searchMs ??
										result?.metadata.timings.engineRoundTripMs,
								},
								{
									label:
										result?.metadata.engine === "coarse"
											? "Contour construction"
											: "Decode & validate",
									value:
										result?.metadata.timings.contourMs ??
										result?.metadata.timings.decodeValidateMs,
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
							{coarse
								? "Grid search includes origin attachment; contour construction traces the reached land cells. "
								: "Engine round trip includes HTTP, graph work, and contouring. "}
							Map idle includes source processing and outstanding map resources;
							it is not a first-paint measurement.
						</p>
						{result && (
							<div className="mt-3 border-t border-[var(--line)] pt-3 text-xs leading-relaxed">
								<p>
									Graph: {result.metadata.graphVersion} · Engine:{" "}
									{result.metadata.engineVersion} ·{" "}
									{result.metadata.engine === "coarse"
										? "Computed in this app"
										: `Upstream GeoJSON: ${(result.metadata.upstreamBytes / 1024).toFixed(1)} KiB`}
								</p>
								<p>
									Coverage: {result.metadata.coverage} · Completeness unverified
								</p>
								{result.metadata.engine === "coarse" ? (
									<>
										<p>
											{result.metadata.approximation?.reachedCells.toLocaleString()}{" "}
											estimated land cells ·{" "}
											{result.metadata.approximation?.gridDegrees}° grid ·
											estimated local travel{" "}
											{result.metadata.approximation?.localSpeedKph} km/h.
										</p>
										<p>{result.metadata.attribution}</p>
										<p>
											<a
												className="underline"
												href="https://www.naturalearthdata.com/"
											>
												Natural Earth
											</a>{" "}
											{result.metadata.approximation?.sourceRelease.includes(
												"Census",
											) && (
												<>
													{" "}
													·{" "}
													<a
														className="underline"
														href="https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html"
													>
														U.S. Census Bureau 2026 TIGER/Line
													</a>
												</>
											)}
										</p>
									</>
								) : result.metadata.engine === "valhalla" ? (
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
										{result.metadata.engine === "coarse"
											? "Model note"
											: "Engine warning"}
										: {warning.description}
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
							Last {maxSavedRuns} queries and run summaries. New saves back up
							automatically when cloud history is available. Replay computes a
							new result.
						</p>
					</div>
					<div className="flex flex-wrap gap-2">
						<button
							className={buttonClass}
							type="button"
							onClick={() => cloudHistory.backup(savedRuns)}
							disabled={
								!savedRuns.length ||
								cloudHistory.status === "loading" ||
								cloudHistory.status === "saving" ||
								cloudHistory.status === "disabled"
							}
						>
							<CloudUpload size={14} />{" "}
							{cloudHistory.status === "offline"
								? "Retry cloud backup"
								: "Back up browser history"}
						</button>
						<button
							className={buttonClass}
							type="button"
							onClick={exportRuns}
							disabled={!savedRuns.length}
						>
							<Download size={14} /> Export JSON
						</button>
					</div>
				</div>
				<output className="mt-3 block text-xs text-[var(--sea-ink-soft)]">
					{cloudHistory.status === "loading"
						? "Loading cloud history…"
						: cloudHistory.status === "saving"
							? "Backing up to the cloud…"
							: cloudHistory.status === "ready"
								? "Cloud backup available for this browser. Older browser history uploads only when you choose Back up browser history."
								: cloudHistory.status === "disabled"
									? "Cloud history is not configured. Queries save in this browser."
									: "Cloud backup unavailable. Queries remain in this browser."}
				</output>
				<p className="mt-1 text-xs text-[var(--sea-ink-soft)]">
					Cloud history is private to this browser. Clearing this site's cookies
					disconnects its cloud history. Cross-device sign-in is coming later.
				</p>
				{cloudHistory.error && (
					<output className="mt-2 block text-sm text-amber-900">
						{cloudHistory.error}
					</output>
				)}
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
										{" · "}
										{cloudHistory.savedIds.has(run.id)
											? "Cloud saved"
											: "Browser only"}
									</p>
								</div>
								<div className="flex gap-2">
									<button
										className={buttonClass}
										type="button"
										onClick={() => {
											const next = getRunModel(run, model);
											updateDraft(toDraft(run.query));
											if (next !== model) {
												setConfig(null);
												setModel(next);
											}
										}}
									>
										Load
									</button>
									<button
										className={buttonClass}
										type="button"
										disabled={
											running ||
											(getRunModel(run, model) !== "coarse" && !canCompute)
										}
										onClick={() =>
											void runQuery(run.query, getRunModel(run, model))
										}
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
				Coarse contours are rough planning estimates. Shaded areas do not
				establish road access, and displayed cell size is not a measured error
				bound. Road-distance and combined-budget semantics, verified coverage,
				spatial layers, and cross-device accounts are upcoming work.
			</footer>
		</main>
	);
}
