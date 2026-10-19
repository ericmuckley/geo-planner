import { createFileRoute } from "@tanstack/react-router";
import {
	getEngineConfig,
	runReachability,
} from "../server/reachability.server";

export const Route = createFileRoute("/api/reachability")({
	server: {
		handlers: {
			GET: () => getEngineConfig(),
			POST: ({ request }) => runReachability(request),
		},
	},
});
