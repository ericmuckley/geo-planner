"""Bounded captured prototype for static single-via-way prohibited sequences.

Keep the entry's from-way context while traversing the via way. Source arc
identity, prices, node rules and every other restriction belong to QueryGraph.
This Python object graph deliberately refuses national-sized inputs.
"""
from collections import Counter
import heapq

from coarse_osm_absent_entry_v1 import plan_entries as absent_plan
from coarse_osm_restriction_entry_v1 import entry_restriction

MAX_STATES = 400000


def plan_contexts(elements, complete_pre_arcs, expected_pre_count):
    proposal = absent_plan(elements, complete_pre_arcs, expected_pre_count)
    converted = {row['id'] for row in proposal['converted'] if row['pairs']}
    rules = [entry_restriction(e) for e in elements if e['id'] in converted]
    assert all(rule is not None for rule in rules)
    assert len(rules) == len(converted)
    return {**proposal, 'contextRules': rules}


class ContextQueryGraph:
    def __init__(self, source_graph, rules):
        rules = list(rules)
        if len(source_graph.arcs) > 200000 or len(source_graph.flags) > 200000 or len(rules) > 10000:
            raise ValueError('Captured context graph bound')
        grouped = {}
        for rule in rules:
            members = rule.from_way, rule.via_way, rule.to_way
            if any(type(w) is not int or w <= 0 for w in members) or rule.via_way in (rule.from_way, rule.to_way):
                raise ValueError('Captured context rule domain')
            grouped.setdefault(members[:2], set()).add(rule.to_way)
        self.prefixes = sorted(grouped)
        self.prefix_index = {key: i for i, key in enumerate(self.prefixes)}
        self.prohibited_to = [frozenset(grouped[key]) for key in self.prefixes]
        counts = Counter(a['way'] for a in source_graph.arcs)
        self.maximum_states = len(source_graph.arcs) + sum(counts[via] for _, via in self.prefixes)
        if self.maximum_states > MAX_STATES:
            raise ValueError('Captured context state bound')
        self.source = source_graph

    def following_context(self, context, before, after):
        a, b = self.source.arcs[before]['way'], self.source.arcs[after]['way']
        if context >= 0:
            assert self.prefixes[context][1] == a
        if a == b:
            return context
        if context >= 0 and b in self.prohibited_to[context]:
            return None
        return self.prefix_index.get((a, b), -1)

    def query(self, source, target, direct=None, check=lambda: None):
        graph = self.source
        stop = {p['arc']: p['ticks'] for p in target.get('partials', ())}
        distances, parents, root_prices, pending = {}, {}, {}, []
        best, finish, settled = direct, ('direct',) if direct is not None else None, 0
        if source.get('vertex', -1) == target.get('vertex', -2):
            best, finish = 0, ('direct',)

        def end(ticks, description):
            nonlocal best, finish
            if ticks <= 345600 and (best is None or ticks < best):
                best, finish = ticks, description

        def offer(arc, context, cost, parent, root=None):
            state = arc, context
            if cost <= 345600 and cost < distances.get(state, 0xffffffff):
                distances[state], parents[state] = cost, parent
                if root is not None:
                    root_prices[state] = root
                heapq.heappush(pending, (cost, arc, context))
                if len(distances) > self.maximum_states or len(pending) > 1000000:
                    raise ValueError('Captured context workspace bound')

        if 'vertex' in source:
            for arc in graph.outgoing[source['vertex']]:
                if arc in stop:
                    end(stop[arc], ('prefix', None, arc))
                cost = (graph.arcs[arc]['ms']+124)//125
                offer(arc, -1, cost, None, ('full', cost))
        else:
            for partial in source['partials']:
                offer(partial['arc'], -1, partial['ticks'], None, ('suffix', partial['ticks']))
        while pending:
            cost, arc, context = heapq.heappop(pending)
            state = arc, context
            if distances[state] != cost:
                continue
            if best is not None and cost > best:
                break
            settled += 1
            if settled > MAX_STATES:
                raise ValueError('Captured context settle bound')
            if settled % 1024 == 0:
                check()
            head = graph.arcs[arc]['head']
            if head == target.get('vertex'):
                end(cost, ('vertex', state))
            for following in graph.outgoing[head]:
                delay = graph.delay(arc, following)
                next_context = self.following_context(context, arc, following)
                if delay is None or next_context is None:
                    continue
                if following in stop:
                    end(cost+delay+stop[following], ('prefix', state, following))
                offer(following, next_context, cost+delay+(graph.arcs[following]['ms']+124)//125, state)
        if finish is None:
            return {'ticks': None, 'steps': [], 'settled': settled}
        if finish[0] == 'direct':
            return {'ticks': best, 'steps': [], 'direct': True, 'settled': settled}
        cursor, reverse_path = finish[1], []
        while cursor is not None:
            reverse_path.append(cursor)
            if len(reverse_path) > self.maximum_states:
                raise ValueError('Captured context parent cycle')
            cursor = parents[cursor]
        steps = []
        for state in reversed(reverse_path):
            arc = state[0]
            kind, ticks = root_prices[state] if not steps else ('full', (graph.arcs[arc]['ms']+124)//125)
            steps.append({'arc': arc, 'kind': kind, 'ticks': ticks})
        if finish[0] == 'prefix':
            steps.append({'arc': finish[2], 'kind': 'prefix', 'ticks': stop[finish[2]]})
        result = {'ticks': best, 'steps': steps, 'settled': settled}
        self.replay(source, target, direct, result)
        return result

    def replay(self, source, target, direct, result):
        self.source.replay(source, target, direct, result)
        context, previous = -1, None
        for step in result['steps']:
            if previous is not None:
                context = self.following_context(context, previous, step['arc'])
                assert context is not None, 'Prohibited via-way completion'
            previous = step['arc']
