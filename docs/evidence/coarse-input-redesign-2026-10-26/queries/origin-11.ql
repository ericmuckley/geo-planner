[out:json][timeout:60][maxsize:268435456][date:"2026-10-21T00:00:00Z"];
way["highway"](34.084700000000005,-116.3631,34.1847,-116.26310000000001)->.roads;
node(w.roads)->.road_nodes;
(
  rel(bw.roads)["type"="restriction"];
  rel(bn.road_nodes)["type"="restriction"];
)->.restrictions;
(.roads; .road_nodes; .restrictions;)->.payload;
.payload out meta;
.payload out count;
