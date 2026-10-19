"""Independent partial-destination oracle without copying the routing graph."""

from fractions import Fraction
from itertools import chain
import math

from maneuver_graph import source_seeds
from queue_oracle import bellman_ford
from state_graph import validate_seeds


class TerminalView:
    def __init__(self, adjacency, entries):
        self.adjacency, self.entries = adjacency, entries

    def __len__(self): return len(self.adjacency) + 1

    def __getitem__(self, state):
        if state == len(self.adjacency): return ()
        if not 0 <= state < len(self.adjacency): raise IndexError(state)
        return chain(self.adjacency[state], self.entries.get(state, ()))


def destination_oracle(graph, seeds, road, fraction, starts):
    """Add only terminal-entry arcs, then independently relax the augmented graph."""
    if type(road) is not int or not 0 <= road < len(graph.base.roads): raise ValueError("Unknown destination road")
    fraction = Fraction(fraction)
    if not 0 < fraction < 1: raise ValueError("Oracle destination must be interior")
    attachments = list(seeds)
    validate_seeds(len(graph.states), attachments)
    sink, full = len(graph.states), graph.base.roads[road]["costMs"]
    partial = math.ceil(full * fraction)
    targets = {index for index, state in enumerate(graph.states) if state["road"] == road}
    entries = {}
    for state, row in enumerate(graph.adjacency):
        for target, weight in row:
            if target in targets:
                cost = weight - full + partial
                if cost < 0: raise ValueError("Terminal entry requires nonnegative routing costs")
                entries.setdefault(state, []).append((sink, cost))
    for source, offset in starts:
        offset = Fraction(offset)
        source_seeds(graph, [(source, offset)])
        if source == road and offset <= fraction:
            attachments.append((sink, math.ceil(full * (fraction - offset))))
    return bellman_ford(TerminalView(graph.adjacency, entries), attachments)[sink]
