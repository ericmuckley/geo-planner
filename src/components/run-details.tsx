import { X } from "lucide-react";
import { useRef } from "react";
import { areaLayers } from "../lib/area-layers";
import type { ReachabilityResult, SavedRun } from "../lib/reachability";

export function RunDetails({
	result,
	run,
}: {
	result: ReachabilityResult | null;
	run: SavedRun | null;
}) {
	const dialogRef = useRef<HTMLDialogElement>(null);
	const metadata = result?.metadata;
	const approximation = metadata?.approximation;
	const timings = [
		{ label: "Grid search", value: metadata?.timings.searchMs },
		{
			label: "Contour construction",
			value: metadata?.timings.contourMs,
		},
		{ label: "Browser request", value: run?.clientRequestMs },
		{ label: "Source → map idle", value: run?.sourceToMapIdleMs },
	];

	return (
		<>
			<button
				type="button"
				className="inline-flex cursor-pointer items-center rounded-sm text-xs font-semibold text-neutral-700 underline decoration-neutral-400 underline-offset-2 hover:text-neutral-950 hover:decoration-neutral-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-700"
				aria-haspopup="dialog"
				onClick={() => dialogRef.current?.showModal()}
			>
				Details
			</button>
			<dialog
				ref={dialogRef}
				aria-labelledby="run-details-title"
				className="fixed inset-0 m-auto max-h-[min(42rem,calc(100dvh-2rem))] w-[calc(100%-2rem)] max-w-xl flex-col overflow-hidden rounded-2xl border border-neutral-200 bg-white p-0 text-neutral-900 shadow-2xl backdrop:bg-black/40 open:flex"
			>
				<header className="flex shrink-0 items-center justify-between gap-3 border-b border-neutral-200 py-3 pr-3 pl-5">
					<h2 id="run-details-title" className="text-base font-bold">
						Estimate details
					</h2>
					<button
						type="button"
						className="flex size-9 items-center justify-center rounded-lg text-neutral-600 hover:bg-neutral-100 focus-visible:outline-2 focus-visible:outline-neutral-700"
						aria-label="Close details"
						onClick={() => dialogRef.current?.close()}
					>
						<X size={18} aria-hidden="true" />
					</button>
				</header>
				<div className="min-h-0 space-y-4 overflow-y-auto overscroll-contain p-5 text-sm leading-relaxed wrap-break-word">
					<p className="rounded-lg bg-neutral-100 p-3 text-neutral-700">
						Approximate planning only. Shading does not establish road access or
						verified driving times.
					</p>
					{metadata && (
						<div className="space-y-2 border-t border-neutral-200 pt-4">
							<p>
								Graph {metadata.graphVersion} · Engine {metadata.engineVersion}
							</p>
							<p>Coverage · {metadata.coverage} · Completeness unverified</p>
							{approximation && (
								<p>
									{approximation.reachedCells.toLocaleString()} estimated land
									cells · {approximation.gridDegrees}° grid · estimated local
									travel {approximation.localSpeedKph} km/h.
								</p>
							)}
							<p>{metadata.attribution}</p>
							<p>
								<a
									className="underline"
									href="https://www.naturalearthdata.com/"
								>
									Natural Earth
								</a>
								{approximation?.sourceRelease.includes("Census") && (
									<>
										{" · "}
										<a
											className="underline"
											href="https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html"
										>
											U.S. Census Bureau 2026 TIGER/Line
										</a>
									</>
								)}
							</p>
						</div>
					)}
					<section className="space-y-2 border-t border-neutral-200 pt-4">
						<h3 className="font-semibold">Area layer sources</h3>
						<ul className="space-y-1">
							{Object.values(areaLayers).map(
								({ attribution, attributionUrl }) => (
									<li key={attribution}>
										<a href={attributionUrl} className="underline">
											{attribution}
										</a>
										{" · Coarse grid (~2 km)"}
									</li>
								),
							)}
						</ul>
					</section>
					{result?.contours.warnings?.map((warning) => (
						<p
							key={`${warning.code}-${warning.description}`}
							className="text-neutral-700"
						>
							{warning.description}
						</p>
					))}
					{result && (
						<section className="space-y-3 border-t border-neutral-200 pt-4">
							<h3 className="font-semibold">Performance</h3>
							<p className="text-xs text-neutral-600">
								{result.query.budgetMinutes} min ·{" "}
								{new Date(result.createdAt).toLocaleTimeString()}
							</p>
							<dl className="grid grid-cols-2 gap-3">
								{timings.map(({ label, value }) => (
									<div key={label}>
										<dt className="text-xs text-neutral-600">{label}</dt>
										<dd className="mt-1 font-mono">
											{value === undefined ? "—" : `${value.toFixed(1)} ms`}
										</dd>
									</div>
								))}
							</dl>
							<p>
								Timings are in milliseconds (ms). 1,000 ms equals one second.
							</p>
							<p>
								Grid search connects the starting point to the grid and finds
								the reachable cells. Contour construction traces the boundary of
								those cells. Browser request measures the time to get and
								validate the server response. Source → map idle measures the
								time from adding the result to the map until pending work like
								loading tiles finishes.
							</p>
						</section>
					)}
					<footer className="border-t border-neutral-200 pt-4">
						<a
							className="underline"
							href="https://github.com/ericmuckley/geo-planner"
							target="_blank"
							rel="noreferrer"
						>
							View project on GitHub
						</a>
					</footer>
				</div>
			</dialog>
		</>
	);
}
