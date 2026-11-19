import { createFileRoute } from "@tanstack/react-router";
import { handlePlaceSearch } from "../server/place-search.server";

export const Route = createFileRoute("/api/place-search")({
	server: {
		handlers: {
			POST: ({ request }) => handlePlaceSearch(request),
		},
	},
});
