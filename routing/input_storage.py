"""Compact decoded OSM inputs; retain the importer's mapping/sequence interface."""

from array import array
from bisect import bisect_left
from collections.abc import Mapping, Sequence
import json
import xml.etree.ElementTree as ET

from import_roads import tags


class IdTable(Mapping):
    def __init__(self):
        self.ids = array("q")
        self.ordered = True
        self.index = None

    def append_id(self, identifier):
        if self.ids and identifier <= self.ids[-1]: self.ordered = False
        self.ids.append(identifier)

    def finish(self):
        # Normal OSM exports are ordered. Keep dict last-write/insertion semantics
        # for unordered or duplicate IDs without burdening the measured ordered case.
        if not self.ordered: self.index = {identifier: i for i, identifier in enumerate(self.ids)}

    def position(self, identifier):
        if self.index is not None: return self.index[identifier]
        position = bisect_left(self.ids, identifier)
        if position == len(self.ids) or self.ids[position] != identifier: raise KeyError(identifier)
        return position

    def __iter__(self): return iter(self.ids if self.index is None else self.index)
    def __len__(self): return len(self.ids if self.index is None else self.index)
    def __contains__(self, identifier):
        try: self.position(identifier)
        except KeyError: return False
        return True

    def storage_summary(self):
        return {"records": len(self), "orderedUniqueIds": self.ordered,
                "fallbackIndexEntries": len(self.index) if self.index is not None else 0,
                "arrayBytes": sum(value.itemsize * len(value) for value in vars(self).values() if isinstance(value, array))}


class NodeRow(Mapping):
    def __init__(self, table, position): self.table, self.position = table, position
    def __iter__(self): return iter(("point", "tags"))
    def __len__(self): return 2
    def __getitem__(self, key):
        if key == "point":
            start = self.position * 2
            return list(self.table.coordinates[start:start + 2])
        if key == "tags": return self.table.properties.get(self.table.ids[self.position], {})
        raise KeyError(key)


class Nodes(IdTable):
    def __init__(self):
        super().__init__()
        self.coordinates, self.properties = array("d"), {}

    def append(self, identifier, point, properties):
        self.append_id(identifier)
        self.coordinates.extend(point)
        if properties: self.properties[identifier] = properties
        else: self.properties.pop(identifier, None)

    def __getitem__(self, identifier): return NodeRow(self, self.position(identifier))
    def storage_summary(self):
        return {**super().storage_summary(), "taggedNodes": len(self.properties)}


class References(Sequence):
    def __init__(self, values, start, end): self.values, self.start, self.end = values, start, end
    def __len__(self): return self.end - self.start
    def __getitem__(self, index):
        if isinstance(index, slice): return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0: index += len(self)
        if not 0 <= index < len(self): raise IndexError(index)
        return self.values[self.start + index]


class WayNodes(Mapping):
    def __init__(self, ways): self.ways = ways
    def __iter__(self): return iter(self.ways)
    def __len__(self): return len(self.ways)
    def __getitem__(self, identifier): return self.ways.references(self.ways.position(identifier))


class Ways(IdTable):
    def __init__(self):
        super().__init__()
        self.offsets, self.nodes = array("Q", [0]), array("q")
        self.tag_offsets, self.tag_bytes = array("Q", [0]), bytearray()

    def append(self, identifier, nodes, properties):
        self.append_id(identifier)
        self.nodes.extend(nodes)
        self.offsets.append(len(self.nodes))
        self.tag_bytes.extend(json.dumps(properties, ensure_ascii=False, separators=(",", ":")).encode())
        self.tag_offsets.append(len(self.tag_bytes))

    def references(self, position): return References(self.nodes, self.offsets[position], self.offsets[position + 1])
    def __getitem__(self, identifier):
        position = self.position(identifier)
        return {"nodes": self.references(position),
                "tags": json.loads(self.tag_bytes[self.tag_offsets[position]:self.tag_offsets[position + 1]])}

    def storage_summary(self):
        return {**super().storage_summary(), "references": len(self.nodes), "encodedTagBytes": len(self.tag_bytes)}


def read_osm(path):
    nodes, ways, relations = Nodes(), Ways(), []
    parser = ET.iterparse(path, events=("start", "end"))
    _, root = next(parser)
    if root.tag != "osm": raise ValueError("Expected an OSM XML document")
    depth = 1
    for event, element in parser:
        if event == "start":
            depth += 1
            continue
        if depth == 2:
            if element.tag == "node":
                nodes.append(int(element.get("id")), [float(element.get("lon")), float(element.get("lat"))], tags(element))
            elif element.tag == "way":
                ways.append(int(element.get("id")), (int(node.get("ref")) for node in element.findall("nd")), tags(element))
            elif element.tag == "relation": relations.append(element)
            root.remove(element)
        depth -= 1
    nodes.finish(); ways.finish()
    return nodes, ways, relations
