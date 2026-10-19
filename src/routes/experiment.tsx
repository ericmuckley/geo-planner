import { createFileRoute, Link } from "@tanstack/react-router";
import {
	AlertTriangle,
	ArrowLeft,
	Download,
	Play,
	RotateCcw,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ResearchMap } from "../components/research-map";
import {
	type ExperimentConfig,
	type ExperimentResult,
	experimentConfigSchema,
	experimentQuerySchema,
	experimentResultSchema,
} from "../lib/experiment";
import { defaultQuery, type Origin, originSchema } from "../lib/reachability";
import { cn } from "../lib/utils";

export const Route = createFileRoute("/experiment")({
	component: ExperimentPage,
});
const field =
	"w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm focus:ring-2 focus:ring-[var(--lagoon-deep)]";
const button =
	"inline-flex items-center justify-center gap-2 rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-45 focus-visible:ring-2 focus-visible:ring-[var(--lagoon-deep)]";
const number = (value: number) =>
	value.toLocaleString(undefined, { maximumFractionDigits: 1 });

function ExperimentPage() {
	const [draft, setDraft] = useState({
		lat: String(defaultQuery.origin.lat),
		lon: String(defaultQuery.origin.lon),
		minutes: "90",
	});
	const [config, setConfig] = useState<ExperimentConfig | null>(null);
	const [result, setResult] = useState<ExperimentResult | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [running, setRunning] = useState(false);
	const [show, setShow] = useState(true);
	const [clientMs, setClientMs] = useState<number | null>(null);
	const [mapMs, setMapMs] = useState<number | null>(null);
	const controller = useRef<AbortController | null>(null);
	const sequence = useRef(0);
	const origin = originSchema.safeParse({
		lat: draft.lat.trim() ? Number(draft.lat) : NaN,
		lon: draft.lon.trim() ? Number(draft.lon) : NaN,
	});
	const parsed = experimentQuerySchema.safeParse({
		origin: origin.success ? origin.data : {},
		budgetMinutes: draft.minutes.trim() ? Number(draft.minutes) : NaN,
	});

	const connect = useCallback(async () => {
		try {
			const response = await fetch("/api/experiment");
			const body = await response.json();
			if (!response.ok)
				throw new Error(body.error || "Local router unavailable");
			setConfig(experimentConfigSchema.parse(body));
			setError(null);
		} catch (cause) {
			setConfig(null);
			setError(
				cause instanceof Error ? cause.message : "Local router unavailable",
			);
		}
	}, []);
	useEffect(() => {
		void connect();
		return () => {
			controller.current?.abort();
		};
	}, [connect]);

	const update = useCallback((patch: Partial<typeof draft>) => {
		sequence.current += 1;
		controller.current?.abort();
		setRunning(false);
		setResult(null);
		setClientMs(null);
		setMapMs(null);
		setDraft((previous) => ({ ...previous, ...patch }));
	}, []);
	const selectOrigin = useCallback(
		(point: Origin) =>
			update({ lat: point.lat.toFixed(6), lon: point.lon.toFixed(6) }),
		[update],
	);

	async function compute() {
		if (!parsed.success || !config) return;
		controller.current?.abort();
		const abort = new AbortController();
		controller.current = abort;
		const request = ++sequence.current;
		setRunning(true);
		setResult(null);
		setError(null);
		setMapMs(null);
		setClientMs(null);
		const before = performance.now();
		try {
			const response = await fetch("/api/experiment", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(parsed.data),
				signal: abort.signal,
			});
			const body = await response.json();
			if (!response.ok) throw new Error(body.error || "Experiment failed");
			const next = experimentResultSchema.parse(body);
			if (sequence.current !== request) return;
			setClientMs(performance.now() - before);
			setResult(next);
		} catch (cause) {
			if (!abort.signal.aborted && sequence.current === request)
				setError(cause instanceof Error ? cause.message : "Experiment failed");
		} finally {
			if (sequence.current === request) setRunning(false);
		}
	}

	function download() {
		if (!result) return;
		const url = URL.createObjectURL(
			new Blob([JSON.stringify(result)], { type: "application/json" }),
		);
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = `geo-planner-experiment-${result.query.budgetMinutes}m.json`;
		anchor.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	const metadata = result?.metadata;
	return (
		<main className="mx-auto max-w-[1600px] p-4 text-[var(--sea-ink)] md:p-7">
			<header className="mb-5 flex flex-wrap items-end justify-between gap-4">
				<div>
					<Link
						to="/"
						className="mb-3 inline-flex items-center gap-1 text-sm underline"
					>
						<ArrowLeft size={15} /> Main workspace
					</Link>
					<p className="island-kicker mb-2">Geo Planner / Offline experiment</p>
					<h1 className="display-title text-3xl md:text-4xl">
						Explore beyond 60 minutes
					</h1>
					<p className="mt-2 text-sm">
						Our local road router · no provider requests · 1–720 minutes
					</p>
				</div>
				<span className="rounded-full border border-[var(--line)] bg-white px-3 py-2 text-xs font-semibold">
					{config ? "Local router connected" : "Local router unavailable"}
				</span>
			</header>
			<div className="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
				<p className="flex items-center gap-2 font-bold">
					<AlertTriangle size={18} /> Experimental regional coverage
				</p>
				<p className="mt-1">
					Routing uses a downloaded region of Southern California and northern
					Baja. The basemap extends beyond our routing data. Longer budgets can
					reach missing roads; red markers show those potential data edges.
					Roads are sampled for display; shaded-area isochrones are not
					generated.
				</p>
				{config && (
					<p className="mt-2 font-semibold">
						Loaded bounds: {config.bounds[1]}°–{config.bounds[3]}° latitude,{" "}
						{config.bounds[0]}°–{config.bounds[2]}° longitude. The dashed
						boundary appears with each result.
					</p>
				)}
			</div>
			<div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
				<aside className="space-y-4">
					<form
						className="island-panel space-y-3 rounded-2xl p-5"
						onSubmit={(event) => {
							event.preventDefault();
							void compute();
						}}
					>
						<h2 className="text-lg font-bold">Driving experiment</h2>
						<label className="block text-sm">
							Latitude
							<input
								className={`${field} mt-1`}
								inputMode="decimal"
								value={draft.lat}
								onChange={(event) => update({ lat: event.target.value })}
							/>
						</label>
						<label className="block text-sm">
							Longitude
							<input
								className={`${field} mt-1`}
								inputMode="decimal"
								value={draft.lon}
								onChange={(event) => update({ lon: event.target.value })}
							/>
						</label>
						<label className="block text-sm">
							Minutes
							<input
								className={`${field} mt-1`}
								type="number"
								min="1"
								max="720"
								step="1"
								value={draft.minutes}
								onChange={(event) => update({ minutes: event.target.value })}
							/>
						</label>
						<div className="flex flex-wrap gap-2">
							{[60, 90, 120, 360, 720].map((minutes) => (
								<button
									key={minutes}
									type="button"
									className={button}
									aria-pressed={draft.minutes === String(minutes)}
									onClick={() => update({ minutes: String(minutes) })}
								>
									{minutes < 360 ? `${minutes}m` : `${minutes / 60}h`}
								</button>
							))}
						</div>
						<button
							type="submit"
							className={cn(
								button,
								"w-full bg-[var(--lagoon-deep)] text-white",
							)}
							disabled={!config || !parsed.success || running}
						>
							<Play size={15} />
							{running
								? "Computing reachable roads…"
								: "Compute reachable roads"}
						</button>
						{!parsed.success && (
							<p className="text-xs text-red-800">
								Enter valid coordinates and 1–720 whole minutes.
							</p>
						)}
						{!config && (
							<button
								type="button"
								className={button}
								onClick={() => void connect()}
							>
								<RotateCcw size={15} /> Retry connection
							</button>
						)}
					</form>
					{error && (
						<p
							role="alert"
							className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900"
						>
							{error}
						</p>
					)}
					{metadata && (
						<section
							aria-label="Experiment results"
							className="island-panel space-y-3 rounded-2xl p-5 text-sm"
						>
							<h2 className="text-lg font-bold">
								{result.query.budgetMinutes}-minute result
							</h2>
							<p
								className={`rounded-lg p-3 font-bold ${metadata.truncated ? "bg-red-50 text-red-900" : "bg-amber-50 text-amber-950"}`}
							>
								{metadata.truncated
									? "Incomplete: dataset boundary reached"
									: "No audited boundary reached; coverage unverified"}
							</p>
							<dl className="space-y-2">
								<div>
									<dt className="text-xs text-[var(--sea-ink-soft)]">
										Reached data-edge nodes
									</dt>
									<dd className="font-bold">
										{metadata.reachedCutNodes} / {metadata.auditedCutNodes}
									</dd>
								</div>
								<div>
									<dt className="text-xs text-[var(--sea-ink-soft)]">
										Directions reached
									</dt>
									<dd>
										{Object.entries(metadata.cutsBySide)
											.map(([side, count]) => `${side}: ${count}`)
											.join(" · ")}
									</dd>
								</div>
								<div>
									<dt className="text-xs text-[var(--sea-ink-soft)]">
										First reached data edge
									</dt>
									<dd>
										{metadata.firstReachedCutMs === null
											? "None within this budget"
											: `${number(metadata.firstReachedCutMs / 60000)} modeled minutes`}
									</dd>
								</div>
								<div>
									<dt className="text-xs text-[var(--sea-ink-soft)]">
										Reachable directed roads
									</dt>
									<dd>{number(metadata.display.reachableDirectedRoads)}</dd>
								</div>
								<div>
									<dt className="text-xs text-[var(--sea-ink-soft)]">
										Displayed road segments (sample)
									</dt>
									<dd>
										{number(metadata.display.displayedSegments)} · every{" "}
										{metadata.display.sampleStride}th reachable road
									</dd>
								</div>
								<div>
									<dt className="text-xs text-[var(--sea-ink-soft)]">
										Origin snap distance
									</dt>
									<dd>{number(metadata.snap.distanceMeters)} m</dd>
								</div>
							</dl>
							<label className="flex items-center gap-2">
								<input
									type="checkbox"
									checked={show}
									onChange={(event) => setShow(event.target.checked)}
								/>{" "}
								Show experimental layers
							</label>
							<button type="button" className={button} onClick={download}>
								<Download size={15} /> Export result
							</button>
							<details>
								<summary className="cursor-pointer font-semibold">
									Measurements and data
								</summary>
								<dl className="mt-2 space-y-1 text-xs">
									<div>
										Native search loop:{" "}
										{number(metadata.timings.nativeSearchMs)} ms
									</div>
									<div>
										Native pipe round trip:{" "}
										{number(metadata.timings.nativeRoundTripMs)} ms
									</div>
									<div>
										Origin snapping: {number(metadata.timings.snapMs)} ms
									</div>
									<div>
										Road display preparation:{" "}
										{number(metadata.timings.geometryMs)} ms
									</div>
									<div>
										Worker total: {number(metadata.timings.workerTotalMs)} ms
									</div>
									<div>
										App round trip:{" "}
										{clientMs === null ? "—" : `${number(clientMs)} ms`}
									</div>
									<div>
										Map update to idle:{" "}
										{mapMs === null ? "—" : `${number(mapMs)} ms`}
									</div>
									<div className="break-all">
										Graph: {metadata.graphIdentity}
									</div>
									<div>OSM snapshot: {metadata.sourceDate}</div>
									<div>Model: {metadata.model}</div>
									<div>© OpenStreetMap contributors · ODbL</div>
								</dl>
							</details>
							<ul className="list-disc space-y-2 pl-4 text-xs text-[var(--sea-ink-soft)]">
								{metadata.warnings.map((warning) => (
									<li key={warning}>{warning}</li>
								))}
							</ul>
						</section>
					)}
				</aside>
				<div className="h-[680px] lg:sticky lg:top-5 lg:h-[calc(100vh-40px)]">
					<ResearchMap
						origin={origin.success ? origin.data : defaultQuery.origin}
						result={null}
						experiment={result}
						showContour={show}
						onOriginChange={selectOrigin}
						onMapIdle={(id, milliseconds) => {
							if (result?.id === id) setMapMs(milliseconds);
						}}
					/>
				</div>
			</div>
		</main>
	);
}
