[out:json][timeout:60][maxsize:268435456][date:"2026-10-21T00:00:00Z"];
way["highway"](33.780300000000004,-116.5953,33.8803,-116.4953)->.roads;
node(w.roads)->.road_nodes;
(
  rel(bw.roads)["type"="restriction"];
  rel(bn.road_nodes)["type"="restriction"];
)->.restrictions;
(.roads; .road_nodes; .restrictions;)->.payload;
.payload out meta;
.payload out count;
