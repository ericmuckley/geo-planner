import { createFileRoute } from "@tanstack/react-router";
import {
	getEstimateConfig,
	runEstimate,
} from "../server/coarse-estimate.server";

export const Route = createFileRoute("/api/estimate")({
	server: {
		handlers: {
			GET: () => getEstimateConfig(),
			POST: ({ request }) => runEstimate(request),
		},
	},
});
