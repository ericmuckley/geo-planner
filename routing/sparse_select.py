"""Select geographic road/restriction seeds with sparse original-ID sets."""

from pathlib import Path
import time

from import_roads import DEFAULT_SPEEDS


def close_parents(selected, parents):
    pending = list(selected)
    while pending:
        for parent in parents.get(pending.pop(), ()):
            if parent not in selected:
                selected.add(parent)
                pending.append(parent)
    return selected


def select_ids(source, bounds, destination, observe=None):
    import osmium

    box = osmium.osm.Box(*bounds)

    class Selector(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.nodes, self.ways, self.roads = set(), set(), set()
            self.relations, self.restrictions, self.parents = set(), set(), {}
            self.counts = {"nodesScanned": 0, "waysScanned": 0, "relationsScanned": 0}
            self.phase = "nodes"

        def node(self, node):
            self.counts["nodesScanned"] += 1
            if box.contains(node.location): self.nodes.add(node.id)
            if observe and self.counts["nodesScanned"] % 10000000 == 0: observe(f"nodes{self.counts['nodesScanned']}")

        def way(self, way):
            if self.phase == "nodes":
                self.phase = "ways"
                if observe: observe("insideNodes")
            self.counts["waysScanned"] += 1
            if any(node.ref in self.nodes for node in way.nodes):
                self.ways.add(way.id)
                if way.tags.get("highway") in DEFAULT_SPEEDS: self.roads.add(way.id)

        def relation(self, relation):
            if self.phase != "relations":
                self.phase = "relations"
                if observe: observe("intersectingWays")
            self.counts["relationsScanned"] += 1
            for member in relation.members:
                if member.type == "r": self.parents.setdefault(member.ref, []).append(relation.id)
                elif (member.type == "n" and member.ref in self.nodes) or (member.type == "w" and member.ref in self.ways):
                    self.relations.add(relation.id)
            if relation.tags.get("type", "").startswith("restriction"): self.restrictions.add(relation.id)

    before = time.perf_counter()
    selection = Selector()
    selection.apply_file(str(source), locations=False)
    close_parents(selection.relations, selection.parents)
    restrictions = selection.relations.intersection(selection.restrictions)
    with Path(destination).open("w") as output:
        for identifier in sorted(selection.roads): output.write(f"w{identifier}\n")
        for identifier in sorted(restrictions): output.write(f"r{identifier}\n")
    return {**selection.counts, "insideNodes": len(selection.nodes), "intersectingWays": len(selection.ways),
            "roadSeeds": len(selection.roads), "restrictionSeeds": len(restrictions), "selectedRelationsIncludingParents": len(selection.relations),
            "wallMs": (time.perf_counter() - before) * 1000,
            "scope": "Sparse sets contain actual original IDs; no location cache, dense highest-ID arrays or remapping. Parent relation closure is recursive; references are completed separately from the original PBF."}
