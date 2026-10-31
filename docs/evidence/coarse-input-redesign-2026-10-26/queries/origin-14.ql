[out:json][timeout:60][maxsize:268435456][date:"2026-10-21T00:00:00Z"];
way["highway"](46.822100000000006,-114.044,46.9221,-113.944)->.roads;
node(w.roads)->.road_nodes;
(
  rel(bw.roads)["type"="restriction"];
  rel(bn.road_nodes)["type"="restriction"];
)->.restrictions;
(.roads; .road_nodes; .restrictions;)->.payload;
.payload out meta;
.payload out count;
