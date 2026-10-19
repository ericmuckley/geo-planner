Help me make a project plan. I have a basic Tanstack Start web app. I'd like to use it to explore some very advanced mapping and isochrone technology.

The goal is to determine new innovative methods for computing isochrones extremely quickly, and displaying them rapidly on a map, ideally in pseudo-real-time.

For example, we should be able to compute large isochrones (up to 12 hours, or using miles instead of hours) from a particular location on the map, and see informative visualizations of the results on the map.

We'll also need geographic information about public lands, businesses, etc.

One initial use-case will be something like: Show me the isochrone area 10 hours (and/or 150 miles) from location X, and highlight all gas stations inside the isochrone, highlight elevations over 5,000 ft, and highlight all public lands which fall within the isochrone.

Our app will need methods for displaying maps, getting other data, and computing geographic information.

Our priority will be using free open-source tools. Postgres is our sql db of choice. Please help me put a high-level plan of action together in terms of which types of technologies, packages/libraries, and mapping data we'll need to fetch and/or compute to be able to satisfy the given use case and similar use cases.