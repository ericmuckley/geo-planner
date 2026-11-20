import { useEffect, useState } from "react";
import { type AreaLayerKind, loadAreaGrid } from "./area-layers";

export function useAreaLayer(
	kind: AreaLayerKind,
	enabled: boolean,
	usedByFilter: boolean,
) {
	const [grid, setGrid] = useState<Uint16Array | null>(null);
	const [loadError, setLoadError] = useState(false);
	const [attempt, setAttempt] = useState(0);
	const needsGrid = enabled || usedByFilter;

	// biome-ignore lint/correctness/useExhaustiveDependencies: Retrying starts a fresh request.
	useEffect(() => {
		if (!needsGrid || grid) return;
		const controller = new AbortController();
		setLoadError(false);
		loadAreaGrid(kind, controller.signal)
			.then((data) => {
				if (!controller.signal.aborted) setGrid(data);
			})
			.catch(() => {
				if (!controller.signal.aborted) setLoadError(true);
			});
		return () => controller.abort();
	}, [needsGrid, grid, kind, attempt]);

	return {
		enabled,
		grid,
		loadError,
		retry: () => setAttempt((current) => current + 1),
	};
}
