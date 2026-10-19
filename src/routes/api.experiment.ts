import { createFileRoute } from "@tanstack/react-router";
import { experimentConfig, runExperiment } from "../server/experiment.server";

export const Route = createFileRoute("/api/experiment")({
	server: {
		handlers: {
			GET: () => experimentConfig(),
			POST: ({ request }) => runExperiment(request),
		},
	},
});
