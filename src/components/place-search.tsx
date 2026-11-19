import { LoaderCircle, Search } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import {
	isStreetAddress,
	type PlaceMatch,
	placeSearchMaxLength,
	placeSearchMinLength,
} from "../lib/place-search";
import { searchPlaces } from "../lib/place-search-client";
import type { Origin } from "../lib/reachability";
import { cn } from "../lib/utils";

type SearchState =
	| { status: "idle" | "loading" }
	| { status: "error"; message: string }
	| { status: "finished"; matches: PlaceMatch[] };

export function PlaceSearch({
	target,
	fieldClass,
	buttonClass,
	onSelect,
}: {
	target: "starting point" | "destination";
	fieldClass: string;
	buttonClass: string;
	onSelect: (point: Origin) => void;
}) {
	const inputId = useId();
	const [query, setQuery] = useState("");
	const [state, setState] = useState<SearchState>({ status: "idle" });
	const controller = useRef<AbortController | null>(null);
	const text = query.trim();
	const address = isStreetAddress(text);

	useEffect(() => () => controller.current?.abort(), []);

	async function submit() {
		if (text.length < placeSearchMinLength) return;
		controller.current?.abort();
		const lookup = new AbortController();
		controller.current = lookup;
		setState({ status: "loading" });
		try {
			const matches = await searchPlaces(text, lookup.signal);
			if (!lookup.signal.aborted) setState({ status: "finished", matches });
		} catch {
			if (!lookup.signal.aborted) {
				setState({
					status: "error",
					message: address
						? "Address search is unavailable. Try again or pick a point on the map."
						: "Place search is unavailable. Try again or pick a point on the map.",
				});
			}
		}
	}

	return (
		<form
			className="space-y-2"
			onSubmit={(event) => {
				event.preventDefault();
				void submit();
			}}
		>
			<label htmlFor={inputId} className="block text-xs font-semibold">
				Search for a {target}
			</label>
			<div className="flex gap-2">
				<input
					id={inputId}
					className={cn(fieldClass, "min-w-0")}
					type="search"
					autoComplete="off"
					placeholder="Town, landmark, or address"
					maxLength={placeSearchMaxLength}
					value={query}
					onChange={(event) => {
						controller.current?.abort();
						setQuery(event.target.value);
						setState({ status: "idle" });
					}}
				/>
				<button
					type="submit"
					aria-label={`Search for a ${target}`}
					disabled={
						text.length < placeSearchMinLength || state.status === "loading"
					}
					className={buttonClass}
				>
					{state.status === "loading" ? (
						<LoaderCircle
							size={15}
							className="animate-spin"
							aria-hidden="true"
						/>
					) : (
						<Search size={15} aria-hidden="true" />
					)}
					Search
				</button>
			</div>
			{address && (
				<p className="text-xs text-[var(--sea-ink-soft)]">
					Address searches use the{" "}
					<a href="https://geocoding.geo.census.gov/" className="underline">
						U.S. Census Geocoder
					</a>
					.
				</p>
			)}
			<div aria-live="polite" className="text-xs text-[var(--sea-ink-soft)]">
				{state.status === "loading" && "Searching…"}
				{state.status === "error" && state.message}
				{state.status === "finished" &&
					(state.matches.length === 0
						? "No matches. Add a state, try a full street address, or pick a point on the map."
						: `${state.matches.length} ${state.matches.length === 1 ? "match" : "matches"}. Pick a result.`)}
			</div>
			{state.status === "finished" && state.matches.length > 0 && (
				<ul
					aria-label={`Search results for the ${target}`}
					className="max-h-48 divide-y divide-[var(--line)] overflow-y-auto rounded-lg border border-[var(--line)] bg-white"
				>
					{state.matches.map((match) => (
						<li
							key={`${match.label}:${match.kind}:${match.point.lat},${match.point.lon}`}
						>
							<button
								type="button"
								className="block w-full px-3 py-2 text-left text-sm hover:bg-[var(--sand)] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--lagoon-deep)]"
								onClick={() => {
									setQuery(match.label);
									setState({ status: "idle" });
									onSelect(match.point);
								}}
							>
								<span className="block font-semibold">{match.label}</span>
								<span className="text-xs text-[var(--sea-ink-soft)]">
									{match.kind}
								</span>
							</button>
						</li>
					))}
				</ul>
			)}
		</form>
	);
}
