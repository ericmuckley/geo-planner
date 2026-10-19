"""Retain compact original road keys, then find restorations by sorted merge."""


class RoadKeys:
    def __init__(self, roads):
        self.ways, self.segments, self.directions = roads.ways, roads.segments, roads.directions
        previous = None
        for index in range(len(self.ways)):
            key = self.key(index)
            if previous is not None and key <= previous:
                raise ValueError("Original road keys must be unique and numerically sorted")
            previous = key

    def key(self, index):
        return self.ways[index], self.segments[index], self.directions[index]

    def summary(self):
        return {"roads": len(self.ways), "payloadBytes": sum(len(values) * values.itemsize for values in (self.ways, self.segments, self.directions)),
                "scope": "Three existing numeric arrays retained by reference; excludes object/allocator overhead. No per-road ID strings or membership set."}

    def restored(self, roads):
        original, previous, restored = 0, None, []
        for index in range(len(roads)):
            key = roads.ways[index], roads.segments[index], roads.directions[index]
            if previous is not None and key <= previous:
                raise ValueError("Final road keys must be unique and numerically sorted")
            previous = key
            while original < len(self.ways) and self.key(original) < key:
                original += 1
            if original == len(self.ways) or self.key(original) != key:
                restored.append(roads[index])
        return restored
