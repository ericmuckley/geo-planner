"""Independent queue-based Bellman-Ford for the nonnegative static routing model."""

from collections import deque
import math

from state_graph import validate_seeds


def bellman_ford(adjacency, seeds):
    """Relax changed labels until stable; no priority queue or Dijkstra calls."""
    validate_seeds(len(adjacency), seeds)
    labels = [math.inf] * len(adjacency)
    queued = bytearray(len(adjacency))
    work = deque()
    for state, cost in seeds:
        if cost < labels[state]: labels[state] = cost
        if not queued[state]:
            work.append(state)
            queued[state] = 1
    while work:
        source = work.popleft()
        queued[source] = 0
        for target, weight in adjacency[source]:
            if weight < 0: raise ValueError("The routing oracle requires nonnegative weights")
            candidate = labels[source] + weight
            if candidate < labels[target]:
                labels[target] = candidate
                if not queued[target]:
                    work.append(target)
                    queued[target] = 1
    return labels
