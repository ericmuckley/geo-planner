import { useCallback, useEffect, useRef, useState } from "react";
import type { SavedRun } from "./reachability";
import { cloudHistorySchema, maxSavedRuns, mergeSavedRuns } from "./saved-runs";

type CloudStatus = "loading" | "ready" | "saving" | "offline" | "disabled";

export function useCloudHistory(onLoad: (runs: SavedRun[]) => void) {
	const [status, setStatus] = useState<CloudStatus>("loading");
	const [error, setError] = useState<string | null>(null);
	const [savedIds, setSavedIds] = useState(new Set<string>());
	const loaded = useRef(onLoad);
	loaded.current = onLoad;
	const lifecycle = useRef<AbortController | null>(null);
	const queue = useRef(Promise.resolve());
	const pending = useRef(new Map<string, SavedRun>());
	const configured = useRef(false);

	const request = useCallback(
		async (signal: AbortSignal, runs?: SavedRun[]) => {
			const response = await fetch("/api/saved-runs", {
				method: runs ? "POST" : "GET",
				credentials: "same-origin",
				headers: runs ? { "Content-Type": "application/json" } : undefined,
				body: runs ? JSON.stringify(runs) : undefined,
				signal,
			});
			const body = await response.json();
			if (typeof body.configured === "boolean")
				configured.current = body.configured;
			if (!response.ok)
				throw new Error(
					typeof body.error === "string"
						? body.error
						: "Cloud history could not be loaded.",
				);
			const result = cloudHistorySchema.parse(body);
			configured.current = result.configured;
			if (!signal.aborted) {
				setSavedIds(new Set(result.runs.map((run) => run.id)));
				loaded.current(result.runs);
				setError(null);
				setStatus(result.configured ? "ready" : "disabled");
			}
		},
		[],
	);

	const flush = useCallback(
		async (signal: AbortSignal) => {
			while (configured.current && pending.current.size && !signal.aborted) {
				const runs = [...pending.current.values()].slice(0, maxSavedRuns);
				setStatus("saving");
				await request(signal, runs);
				for (const run of runs)
					if (pending.current.get(run.id) === run)
						pending.current.delete(run.id);
			}
		},
		[request],
	);

	const enqueue = useCallback(
		(task: (signal: AbortSignal) => Promise<void>) => {
			const signal = lifecycle.current?.signal;
			if (!signal) return;
			queue.current = queue.current
				.then(async () => {
					if (!signal.aborted) await task(signal);
				})
				.catch((cause) => {
					if (!signal.aborted) {
						setStatus("offline");
						setError(
							cause instanceof Error
								? cause.message
								: "Cloud history is unavailable. Queries remain in this browser.",
						);
					}
				});
		},
		[],
	);

	useEffect(() => {
		const controller = new AbortController();
		lifecycle.current = controller;
		queue.current = Promise.resolve();
		enqueue((signal) => request(signal));
		return () => controller.abort();
	}, [enqueue, request]);

	const addPending = useCallback((runs: SavedRun[]) => {
		pending.current = new Map(
			mergeSavedRuns(runs, [...pending.current.values()]).map((run) => [
				run.id,
				run,
			]),
		);
	}, []);
	const save = useCallback(
		(run: SavedRun) => {
			addPending([run]);
			enqueue(flush);
		},
		[addPending, enqueue, flush],
	);
	const backup = useCallback(
		(runs: SavedRun[]) => {
			addPending(runs);
			enqueue(async (signal) => {
				setStatus("loading");
				await request(signal);
				await flush(signal);
			});
		},
		[addPending, enqueue, flush, request],
	);

	return { status, error, savedIds, save, backup };
}
