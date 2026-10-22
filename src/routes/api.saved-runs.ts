import { createFileRoute } from "@tanstack/react-router";
import { handleSavedRuns } from "../server/saved-runs.server";

export const Route = createFileRoute("/api/saved-runs")({
	server: {
		handlers: {
			GET: ({ request }) => handleSavedRuns(request),
			POST: ({ request }) => handleSavedRuns(request),
		},
	},
});
