import { useEffect, useState } from "react";
import { type AreaLayerKind, loadAreaGrid } from "./area-layers";

export function useAreaLayer(kind: AreaLayerKind) {
	const [enabled, setEnabled] = useState(false);
	const [grid, setGrid] = useState<Uint16Array | null>(null);
	const [loadError, setLoadError] = useState(false);

	useEffect(() => {
		if (!enabled || grid) return;
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
	}, [enabled, grid, kind]);

	return { enabled, setEnabled, grid: enabled ? grid : null, loadError };
}
