import { ChevronDown, LocateFixed } from "lucide-react";
import { useMemo, useState } from "react";
import {
	type OutdoorPlaceKind,
	type OutdoorPlaceSelection,
	type PlaceLocations,
	placeLayers,
} from "../lib/place-locations";

const pageSize = 20;

export function OutdoorPlaceResults({
	kind,
	locations,
	onSelect,
}: {
	kind: OutdoorPlaceKind;
	locations: PlaceLocations;
	onSelect: (selection: OutdoorPlaceSelection) => void;
}) {
	const [open, setOpen] = useState(false);
	const [limit, setLimit] = useState(pageSize);
	const label = placeLayers[kind].label.toLowerCase();
	const sorted = useMemo(
		() =>
			open
				? [...locations.features].sort((first, second) =>
						first.properties.name.localeCompare(second.properties.name),
					)
				: [],
		[open, locations],
	);

	return (
		<details
			className="group rounded-lg border border-[var(--line)]"
			onToggle={(event) => setOpen(event.currentTarget.open)}
		>
			<summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-sm font-semibold [&::-webkit-details-marker]:hidden">
				Browse {label}
				<ChevronDown
					size={15}
					className="shrink-0 group-open:rotate-180"
					aria-hidden="true"
				/>
			</summary>
			{open && (
				<div className="border-t border-[var(--line)]">
					<ul
						aria-label={`Matching ${label}`}
						className="divide-y divide-[var(--line)]"
					>
						{sorted.slice(0, limit).map((location) => (
							<li key={location.id}>
								<button
									type="button"
									className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--sand)] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--lagoon-deep)]"
									onClick={() => onSelect({ kind, location })}
								>
									{location.properties.name}
									<LocateFixed
										size={14}
										className="shrink-0"
										aria-hidden="true"
									/>
								</button>
							</li>
						))}
					</ul>
					{sorted.length > limit && (
						<button
							type="button"
							className="w-full border-t border-[var(--line)] px-3 py-2 text-left text-xs font-semibold text-[var(--lagoon-deep)] hover:bg-[var(--sand)]"
							onClick={() => setLimit((current) => current + pageSize)}
						>
							Show more {label}
						</button>
					)}
				</div>
			)}
		</details>
	);
}
