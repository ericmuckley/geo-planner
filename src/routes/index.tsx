import {
	createFileRoute,
	type SearchSchemaInput,
	useLocation,
} from "@tanstack/react-router";
import {
	ChevronUp,
	LoaderCircle,
	MapPin,
	PanelLeftClose,
	PanelLeftOpen,
	SlidersHorizontal,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AreaLayerControls } from "../components/area-layer-controls";
import { OutdoorPlaceFilters } from "../components/outdoor-place-filters";
import {
	PlaceDataAttribution,
	PlaceLayerControls,
} from "../components/place-layer-controls";
import { ResearchMap } from "../components/research-map";
import { RunDetails } from "../components/run-details";
import type { AreaLayerKind, ElevationRange } from "../lib/area-layers";
import { type MapSearch, validateMapSearch } from "../lib/map-search";
import {
	type OutdoorPlaceSelection,
	type PlaceKind,
	placeTerrainFilter,
} from "../lib/place-locations";
import {
	defaultQuery,
	type EngineConfig,
	engineConfigSchema,
	type Origin,
	type ReachabilityQuery,
	type ReachabilityResult,
	resultSchema,
	type SavedRun,
} from "../lib/reachability";
import {
	mergeSavedRuns,
	readSavedRuns,
	writeSavedRuns,
} from "../lib/saved-runs";
import { useAreaLayer } from "../lib/use-area-layer";
import { useCloudHistory } from "../lib/use-cloud-history";
import { usePlaceLayer } from "../lib/use-place-layer";
import { cn } from "../lib/utils";

export const Route = createFileRoute("/")({
	validateSearch: (search: Partial<MapSearch> & SearchSchemaInput) =>
		validateMapSearch(search),
	component: Home,
});

const estimateEndpoint = "/api/estimate";

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
	const search = Route.useSearch();
	const navigate = Route.useNavigate();
	const hasSearch = useLocation({
		select: (location) => Boolean(location.searchStr),
	});
	const {
		lat,
		lon,
		minutes,
		minElevation,
		maxElevation,
		publicLandOnly,
		elevationOnly,
	} = search;
	const origin = useMemo(() => ({ lat, lon }), [lat, lon]);
	const query = useMemo(
		() => ({ ...defaultQuery, origin, budgetMinutes: minutes }),
		[origin, minutes],
	);
	const updateSearch = useCallback(
		(updates: Partial<MapSearch>, replace = false) => {
			void navigate({
				search: (current) => ({ ...current, ...updates }),
				replace,
				resetScroll: false,
			});
		},
		[navigate],
	);
	useEffect(() => {
		if (!hasSearch) updateSearch(validateMapSearch({}), true);
	}, [hasSearch, updateSearch]);

	const [controlsOpen, setControlsOpen] = useState(true);
	const [mobileControlsOpen, setMobileControlsOpen] = useState(false);
	const controlsRef = useRef<HTMLElement>(null);
	const mobileControlsButton = useRef<HTMLButtonElement>(null);
	const [minutesDraft, setMinutesDraft] = useState<number | null>(null);
	const budgetMinutes = minutesDraft ?? minutes;
	const [config, setConfig] = useState<EngineConfig | null>(null);
	const [configError, setConfigError] = useState(false);
	const [result, setResult] = useState<ReachabilityResult | null>(null);
	const landLayer = useAreaLayer("land", search.land, publicLandOnly);
	const elevationLayer = useAreaLayer(
		"elevation",
		search.elevation,
		elevationOnly,
	);
	const elevationRange = useMemo<ElevationRange>(
		() => [minElevation, maxElevation],
		[minElevation, maxElevation],
	);
	const elevationSlider = {
		value: elevationRange,
		onChange: ([minElevation, maxElevation]: ElevationRange) =>
			updateSearch({ minElevation, maxElevation }, true),
	};
	const filterLand = publicLandOnly ? landLayer.grid : undefined;
	const filterElevation = elevationOnly ? elevationRange : undefined;
	const outdoorFilter = useMemo(
		() =>
			placeTerrainFilter(
				filterLand,
				filterElevation === undefined
					? undefined
					: { grid: elevationLayer.grid, range: filterElevation },
			),
		[filterLand, filterElevation, elevationLayer.grid],
	);
	const fuelLayer = usePlaceLayer("fuel", search.fuel, result?.contours);
	const trailheadLayer = usePlaceLayer(
		"trailheads",
		search.trailheads,
		result?.contours,
		outdoorFilter,
	);
	const campgroundLayer = usePlaceLayer(
		"campgrounds",
		search.campgrounds,
		result?.contours,
		outdoorFilter,
	);
	const placeLayers = {
		fuel: fuelLayer,
		trailheads: trailheadLayer,
		campgrounds: campgroundLayer,
	};
	const outdoorFiltersActive = publicLandOnly || elevationOnly;
	const showOutdoorFilters =
		trailheadLayer.enabled || campgroundLayer.enabled || outdoorFiltersActive;
	const [selectedOutdoorPlace, setSelectedOutdoorPlace] =
		useState<OutdoorPlaceSelection | null>(null);
	const [activeRun, setActiveRun] = useState<SavedRun | null>(null);
	const [savedRuns, setSavedRuns] = useState<SavedRun[]>([]);
	const [historyDirty, setHistoryDirty] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [running, setRunning] = useState(false);
	const [cancelled, setCancelled] = useState(false);
	const loadCloudRuns = useCallback((runs: SavedRun[]) => {
		setSavedRuns((current) => mergeSavedRuns(current, runs));
		setHistoryDirty(true);
	}, []);
	const { save: saveCloudRun } = useCloudHistory(loadCloudRuns);
	const canCompute = config?.configured && config.health === "ready";
	const estimateError =
		configError || (config && !canCompute)
			? "Could not load estimate settings. Reload the page to try again."
			: error;
	const controller = useRef<AbortController | null>(null);
	const sequence = useRef(0);
	const pendingMinutes = useRef<number | null>(null);
	const requestedQuery = useRef<ReachabilityQuery | null>(null);
	const minMinutes = config?.minMinutes ?? 30;
	const maxMinutes = config?.maxMinutes ?? 720;

	useEffect(() => {
		const abort = new AbortController();
		fetch(estimateEndpoint, { signal: abort.signal })
			.then(async (response) => {
				if (!response.ok) throw new Error("Could not load estimate settings.");
				return engineConfigSchema.parse(await response.json());
			})
			.then(setConfig)
			.catch(() => {
				if (!abort.signal.aborted) setConfigError(true);
			});
		return () => abort.abort();
	}, []);

	useEffect(() => {
		try {
			setSavedRuns(readSavedRuns());
		} catch {
			// Estimates still work when browser history is unreadable.
		}
		return () => controller.current?.abort();
	}, []);

	useEffect(() => {
		if (!historyDirty) return;
		try {
			writeSavedRuns(savedRuns);
		} catch {
			// Keep runs in memory when browser storage is unavailable.
		}
	}, [savedRuns, historyDirty]);

	const clearResult = useCallback(() => {
		pendingMinutes.current = null;
		setMinutesDraft(null);
		sequence.current += 1;
		controller.current?.abort();
		setRunning(false);
		setCancelled(false);
		setResult(null);
		setActiveRun(null);
		setSelectedOutdoorPlace(null);
		setError(null);
	}, []);
	const selectOrigin = useCallback(
		(selected: Origin) => {
			if (selected.lat === origin.lat && selected.lon === origin.lon) return;
			requestedQuery.current = { ...query, origin: selected };
			clearResult();
			updateSearch(selected);
		},
		[clearResult, origin, query, updateSearch],
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

	const runQuery = useCallback(
		async (query: ReachabilityQuery, save: boolean) => {
			controller.current?.abort();
			const abort = new AbortController();
			controller.current = abort;
			const requestNumber = ++sequence.current;
			setRunning(true);
			setCancelled(false);
			setResult(null);
			setActiveRun(null);
			setError(null);
			const started = performance.now();
			try {
				const response = await fetch(estimateEndpoint, {
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
				if (abort.signal.aborted || sequence.current !== requestNumber) return;
				const run: SavedRun = {
					id: next.id,
					createdAt: next.createdAt,
					query: next.query,
					model: "coarse",
					metadata: next.metadata,
					clientRequestMs: performance.now() - started,
				};
				setResult(next);
				setActiveRun(run);
				if (save) {
					setSavedRuns((runs) => mergeSavedRuns([run], runs));
					setHistoryDirty(true);
					saveCloudRun(run);
				}
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
		},
		[saveCloudRun],
	);

	useEffect(() => {
		clearResult();
		const { budgetMinutes, origin } = query;
		if (!canCompute || budgetMinutes < minMinutes || budgetMinutes > maxMinutes)
			return;
		const requested = requestedQuery.current;
		requestedQuery.current = null;
		// Automatic loads and browser history navigation do not create saved runs.
		const save =
			requested?.origin.lat === origin.lat &&
			requested.origin.lon === origin.lon &&
			requested.budgetMinutes === budgetMinutes;
		void runQuery(query, save);
	}, [clearResult, canCompute, query, minMinutes, maxMinutes, runQuery]);

	function commitDrivingTime() {
		const pending = pendingMinutes.current;
		pendingMinutes.current = null;
		setMinutesDraft(null);
		if (pending === null || pending === minutes) return;
		requestedQuery.current = { ...query, budgetMinutes: pending };
		updateSearch({ minutes: pending });
	}

	function changeLayer(kind: AreaLayerKind | PlaceKind, checked: boolean) {
		updateSearch({ [kind]: checked });
	}

	return (
		<main className="fixed inset-0 isolate flex flex-col overflow-hidden bg-neutral-100 text-neutral-900">
			<div className="relative min-h-0 flex-1">
				<div className="absolute inset-0" aria-busy={running}>
					<ResearchMap
						origin={origin}
						result={result}
						selectedOutdoorPlace={selectedOutdoorPlace}
						landGrid={landLayer.enabled ? landLayer.grid : null}
						elevationGrid={elevationLayer.enabled ? elevationLayer.grid : null}
						elevationRange={elevationRange}
						places={{
							fuel: fuelLayer.locations,
							trailheads: trailheadLayer.locations,
							campgrounds: campgroundLayer.locations,
						}}
						showContour
						onOriginChange={selectOrigin}
						onMapIdle={onMapIdle}
						fullscreen
						overlayRef={controlsRef}
					/>
				</div>
				{running && (
					<output className="pointer-events-none absolute inset-x-0 bottom-14 z-10 flex justify-center">
						<span className="flex items-center gap-2 rounded-full border border-neutral-200 bg-white/95 px-4 py-2.5 text-sm font-semibold shadow-lg">
							<LoaderCircle
								className="animate-spin"
								size={16}
								aria-hidden="true"
							/>
							Updating area…
						</span>
					</output>
				)}
			</div>
			<aside
				ref={controlsRef}
				aria-label="Map controls"
				className="z-20 flex max-h-[50dvh] shrink-0 flex-col overflow-hidden border-t border-neutral-200 bg-white pb-[env(safe-area-inset-bottom)] shadow-lg shadow-black/10 [&_a]:text-neutral-700! [&_a]:decoration-neutral-400! [&_a:hover]:text-black! planner-wide:absolute planner-wide:top-5 planner-wide:left-5 planner-wide:max-h-[calc(100dvh-5rem)] planner-wide:w-80 planner-wide:rounded-2xl planner-wide:border planner-wide:pb-0"
			>
				<button
					ref={mobileControlsButton}
					type="button"
					className="flex min-h-16 shrink-0 cursor-pointer items-center gap-3 px-4 py-2 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neutral-700 planner-wide:hidden"
					onClick={() => setMobileControlsOpen((open) => !open)}
					aria-expanded={mobileControlsOpen}
					aria-controls="trip-controls"
				>
					<span className="grid size-10 shrink-0 place-items-center rounded-xl bg-[var(--sand)] text-[var(--sea-ink)]">
						<SlidersHorizontal size={19} aria-hidden="true" />
					</span>
					<span className="min-w-0 flex-1">
						<span className="block text-sm font-bold">Trip controls</span>
						<span className="block text-xs text-neutral-600">
							{formatDuration(budgetMinutes)} of driving
						</span>
					</span>
					<ChevronUp
						size={20}
						className={cn(
							"shrink-0 text-neutral-600",
							mobileControlsOpen && "rotate-180",
						)}
						aria-hidden="true"
					/>
				</button>
				<div
					id="trip-controls"
					className={cn(
						"min-h-0 overflow-y-auto overscroll-contain planner-wide:flex planner-wide:flex-col planner-wide:overflow-hidden",
						!mobileControlsOpen && "hidden",
					)}
				>
					<div className="flex shrink-0 items-center gap-2.5 px-4 py-3">
						<div className="hidden size-7 shrink-0 items-center justify-center rounded-md bg-neutral-900 text-white planner-wide:flex">
							<MapPin size={16} aria-hidden="true" />
						</div>
						<div className="flex min-w-0 flex-1 items-center justify-between gap-2 planner-wide:block">
							<h1 className="text-xs font-bold">
								<span className="planner-wide:hidden">
									Tap map to set starting point
								</span>
								<span className="hidden planner-wide:inline">
									Click map to set starting location
								</span>
							</h1>
							<RunDetails result={result} run={activeRun} />
						</div>
						<button
							type="button"
							className="hidden size-9 shrink-0 items-center justify-center rounded-lg text-neutral-600 hover:bg-neutral-100 focus-visible:outline-2 focus-visible:outline-neutral-700 planner-wide:flex"
							onClick={() => setControlsOpen((open) => !open)}
							aria-expanded={controlsOpen}
							aria-controls="map-controls-content"
							aria-label={
								controlsOpen ? "Collapse controls" : "Expand controls"
							}
							title={controlsOpen ? "Collapse controls" : "Expand controls"}
						>
							{controlsOpen ? (
								<PanelLeftClose size={18} />
							) : (
								<PanelLeftOpen size={18} />
							)}
						</button>
					</div>
					<div
						id="map-controls-content"
						className={cn(
							"planner-wide:min-h-0 planner-wide:flex-col",
							controlsOpen ? "planner-wide:flex" : "planner-wide:hidden",
						)}
					>
						<div className="border-t border-neutral-200 planner-wide:min-h-0 planner-wide:overflow-y-auto planner-wide:overscroll-contain">
							<section
								className="flex flex-col gap-2 p-4"
								aria-labelledby="driving-time-label"
							>
								<div>
									<label
										className="block text-xs font-semibold"
										htmlFor="minutes"
									>
										<span className="flex items-center justify-between gap-2">
											<span id="driving-time-label">
												Driving time within {formatDuration(budgetMinutes)}
											</span>
										</span>
									</label>
									<input
										id="minutes"
										className="block h-9 w-full cursor-pointer accent-neutral-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 planner-wide:h-5"
										type="range"
										aria-label="Driving time"
										aria-valuetext={formatDuration(budgetMinutes)}
										min={minMinutes}
										max={maxMinutes}
										step={1}
										value={budgetMinutes}
										disabled={!canCompute}
										onChange={(event) => {
											const minutes = event.currentTarget.valueAsNumber;
											pendingMinutes.current = minutes;
											setMinutesDraft(minutes);
										}}
										onPointerDown={(event) =>
											event.currentTarget.setPointerCapture(event.pointerId)
										}
										onPointerUp={commitDrivingTime}
										onKeyUp={commitDrivingTime}
										onBlur={commitDrivingTime}
										onPointerCancel={() => {
											pendingMinutes.current = null;
											setMinutesDraft(null);
										}}
									/>
									<div
										className="-mt-1 flex justify-between text-xs text-neutral-600"
										aria-hidden="true"
									>
										<span>{formatDuration(minMinutes)}</span>
										<span>{formatDuration(maxMinutes)}</span>
									</div>
								</div>
								{estimateError && (
									<p
										role="alert"
										className="rounded-lg border border-neutral-200 bg-neutral-100 p-3 text-sm"
									>
										{estimateError}
									</p>
								)}
								{(running || (canCompute && (error || cancelled))) && (
									<button
										type="button"
										className="min-h-7 self-start cursor-pointer rounded-sm text-xs font-semibold underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2"
										onClick={() => {
											if (running) {
												clearResult();
												setCancelled(true);
											} else {
												void runQuery(query, true);
											}
										}}
									>
										{running ? "Cancel estimate" : "Retry estimate"}
									</button>
								)}
							</section>
							<PlaceLayerControls
								layers={placeLayers}
								onLayerChange={changeLayer}
								filtersActive={outdoorFiltersActive}
								filtersPending={Boolean(result) && outdoorFilter === null}
								onOutdoorPlaceSelect={(selection) => {
									setSelectedOutdoorPlace(selection);
									setMobileControlsOpen(false);
									mobileControlsButton.current?.focus({ preventScroll: true });
								}}
								outdoorFilters={
									showOutdoorFilters && (
										<OutdoorPlaceFilters
											publicLandOnly={publicLandOnly}
											onPublicLandOnlyChange={(checked) =>
												updateSearch({ publicLandOnly: checked })
											}
											elevationOnly={elevationOnly}
											onElevationOnlyChange={(checked) =>
												updateSearch({ elevationOnly: checked })
											}
											elevationSlider={elevationSlider}
											land={landLayer}
											elevation={elevationLayer}
										/>
									)
								}
							/>
							<AreaLayerControls
								land={landLayer}
								elevation={elevationLayer}
								onLayerChange={changeLayer}
								elevationSlider={elevationOnly ? undefined : elevationSlider}
							/>
						</div>
						<PlaceDataAttribution layers={placeLayers} />
					</div>
				</div>
			</aside>
		</main>
	);
}
