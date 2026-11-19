import { Crosshair } from "lucide-react";
import { useMemo, useState } from "react";
import { isInEstimatedArea } from "../lib/contour-membership";
import {
	type Origin,
	originSchema,
	type ReachabilityResult,
} from "../lib/reachability";
import { cn } from "../lib/utils";
import { PlaceSearch } from "./place-search";

type Props = {
	result: ReachabilityResult | null;
	destination: Origin | null;
	picking: boolean;
	running: boolean;
	fieldClass: string;
	buttonClass: string;
	onTogglePick: () => void;
	onChange: (destination: Origin | null) => void;
};

export function DestinationCheck({
	result,
	destination,
	picking,
	running,
	fieldClass,
	buttonClass,
	onTogglePick,
	onChange,
}: Props) {
	const [lat, setLat] = useState("");
	const [lon, setLon] = useState("");
	const point = originSchema.safeParse({
		lat: lat.trim() ? Number(lat) : NaN,
		lon: lon.trim() ? Number(lon) : NaN,
	});
	const contours = result?.contours;
	const inside = useMemo(
		() =>
			destination && contours ? isInEstimatedArea(destination, contours) : null,
		[destination, contours],
	);
	return (
		<section
			aria-labelledby="destination-heading"
			className="space-y-3 bg-[var(--sand)]/60 p-4 border-t border-[var(--line)]"
		>
			<h2
				id="destination-heading"
				className="flex items-center gap-2 text-sm font-bold"
			>
				<Crosshair size={16} aria-hidden="true" /> Check a destination
			</h2>
			<PlaceSearch
				target="destination"
				fieldClass={fieldClass}
				buttonClass={buttonClass}
				onSelect={(point) => {
					setLat(point.lat.toFixed(6));
					setLon(point.lon.toFixed(6));
					onChange(point);
				}}
			/>
			<button
				type="button"
				onClick={onTogglePick}
				className={cn(
					buttonClass,
					picking && "bg-[var(--lagoon-deep)] text-white",
				)}
			>
				{picking ? "Cancel map selection" : "Pick on map"}
			</button>
			{picking && (
				<output className="block text-xs">
					Click a destination on the map.
				</output>
			)}
			<form
				className="space-y-2"
				onSubmit={(event) => {
					event.preventDefault();
					if (point.success) onChange(point.data);
				}}
			>
				<div className="grid grid-cols-2 gap-3 text-xs font-semibold">
					<label className="space-y-1">
						<span>Destination latitude</span>
						<input
							className={fieldClass}
							type="number"
							step="any"
							min={-85}
							max={85}
							required
							value={lat}
							onChange={(event) => setLat(event.target.value)}
						/>
					</label>
					<label className="space-y-1">
						<span>Destination longitude</span>
						<input
							className={fieldClass}
							type="number"
							step="any"
							min={-180}
							max={180}
							required
							value={lon}
							onChange={(event) => setLon(event.target.value)}
						/>
					</label>
				</div>
				<button type="submit" disabled={!point.success} className={buttonClass}>
					Check coordinates
				</button>
			</form>
			{destination && (
				<div className="flex items-start justify-between gap-2 text-xs">
					<output className="space-y-1" aria-live="polite">
						<span className="block font-semibold">
							{inside === null
								? running
									? "Updating destination check…"
									: "Estimate an area to check this point."
								: inside
									? "Inside the estimated area"
									: "Outside the estimated area"}
						</span>
						<span>
							{destination.lat.toFixed(5)}, {destination.lon.toFixed(5)}
						</span>
					</output>
					<button
						type="button"
						className="font-semibold text-[var(--lagoon-deep)]"
						onClick={() => {
							setLat("");
							setLon("");
							onChange(null);
						}}
					>
						Clear
					</button>
				</div>
			)}
		</section>
	);
}
