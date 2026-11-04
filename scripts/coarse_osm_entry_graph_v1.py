"""Small captured-fact graph experiment; explicitly refuses national inputs."""
from collections import defaultdict
import heapq

from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_restriction_entry_v1 import entry_pairs, entry_restriction


def plan_entries(elements, arcs):
    if len(elements) > 10000 or len(arcs) > 200000:
        raise ValueError('Captured entry graph bound')
    grouped = defaultdict(list)
    for i, a in enumerate(arcs):
        grouped[a['way']].append({**a, 'id': i})
    present = set(grouped)
    old_closed, closed, pairs, converted, fallback = set(), set(), set(), [], []
    for e in elements:
        original = restriction_policy(e)
        if original['status'] != 'closed-unsupported':
            continue
        old_closed.update(original['memberWays'])
        rule = entry_restriction(e)
        found = None if rule is None else entry_pairs(rule, grouped[rule.from_way], grouped[rule.via_way], present)
        if found is None:
            closed.update(original['memberWays'])
            fallback.append(e['id'])
        else:
            pairs.update(found)
            converted.append({'id': e['id'], 'pairs': found})
    assert closed <= old_closed
    return {'oldClosed': old_closed, 'closed': closed, 'pairs': pairs, 'converted': converted, 'fallback': fallback}


class QueryGraph:
    """Unquantized source facts stay attached; all search prices are125ms ticks."""
    def __init__(self, arcs, flags, forbidden):
        forbidden = set(forbidden)
        if len(arcs) > 200000 or len(flags) > 200000 or len(forbidden) > 2000000:
            raise ValueError('Captured query graph bound')
        self.arcs, self.flags, self.forbidden = arcs, flags, set(forbidden)
        self.outgoing = [[] for _ in flags]
        lookup = {(a['way'], a['first'], a['last'], a['direction']): i for i, a in enumerate(arcs)}
        assert len(lookup) == len(arcs)
        self.reverse = []
        for i, a in enumerate(arcs):
            assert 0 <= a['tail'] < len(flags) and 0 <= a['head'] < len(flags)
            assert 0 < a['ms'] <= 0xffffffff*125
            self.outgoing[a['tail']].append(i)
            self.reverse.append(lookup.get((a['way'], a['first'], a['last'], -a['direction'])))

    def delay(self, before, after):
        a, b = self.arcs[before], self.arcs[after]
        assert a['head'] == b['tail']
        flags = self.flags[a['head']]
        reverse = self.reverse[before] == after
        if flags & 1 or reverse and not flags & 4 or (before, after) in self.forbidden:
            return None
        return (40 if flags & 2 else 0) + (160 if reverse else 0)

    def query(self, source, target, direct=None, check=lambda: None):
        stop = {a['arc']: a['ticks'] for a in target.get('partials', ())}
        distances, parents, root_prices, pending = {}, {}, {}, []
        best, finish, settled = direct, ('direct',) if direct is not None else None, 0
        if source.get('vertex', -1) == target.get('vertex', -2):
            best, finish = 0, ('direct',)

        def end(ticks, description):
            nonlocal best, finish
            if ticks <= 345600 and (best is None or ticks < best):
                best, finish = ticks, description

        def offer(arc, cost, parent, root=None):
            if cost <= 345600 and cost < distances.get(arc, 0xffffffff):
                distances[arc], parents[arc] = cost, parent
                if root is not None:
                    root_prices[arc] = root
                heapq.heappush(pending, (cost, arc))
                if len(pending) > 1000000:
                    raise ValueError('Captured query heap cap')

        if 'vertex' in source:
            for i in self.outgoing[source['vertex']]:
                if i in stop:
                    end(stop[i], ('prefix', None, i))
                cost = (self.arcs[i]['ms']+124)//125
                offer(i, cost, None, ('full', cost))
        else:
            for s in source['partials']:
                offer(s['arc'], s['ticks'], None, ('suffix', s['ticks']))
        while pending:
            cost, i = heapq.heappop(pending)
            if distances[i] != cost:
                continue
            if best is not None and cost > best:
                break
            settled += 1
            if settled > 200000:
                raise ValueError('Captured query settle cap')
            if settled % 1024 == 0:
                check()
            a = self.arcs[i]
            if a['head'] == target.get('vertex'):
                end(cost, ('vertex', i))
            for j in self.outgoing[a['head']]:
                delay = self.delay(i, j)
                if delay is None:
                    continue
                if j in stop:
                    end(cost+delay+stop[j], ('prefix', i, j))
                offer(j, cost+delay+(self.arcs[j]['ms']+124)//125, i)
        if finish is None:
            return {'ticks': None, 'steps': [], 'settled': settled}
        if finish[0] == 'direct':
            return {'ticks': best, 'steps': [], 'direct': True, 'settled': settled}
        cursor = finish[1]
        reverse_path = []
        while cursor is not None:
            reverse_path.append(cursor)
            if len(reverse_path) > len(self.arcs):
                raise ValueError('Captured path parent cycle')
            cursor = parents[cursor]
        steps = []
        for i in reversed(reverse_path):
            kind, ticks = root_prices[i] if not steps else ('full', (self.arcs[i]['ms']+124)//125)
            steps.append({'arc': i, 'kind': kind, 'ticks': ticks})
        if finish[0] == 'prefix':
            steps.append({'arc': finish[2], 'kind': 'prefix', 'ticks': stop[finish[2]]})
        # Search/replay remain separate. The source audit adds original-relation
        # and native geometry/partial checks after this price/graph replay.
        self.replay(source, target, direct, {'ticks': best, 'steps': steps})
        return {'ticks': best, 'steps': steps, 'settled': settled}

    def replay(self, source, target, direct, result):
        if result['ticks'] is None:
            assert not result['steps']
            return
        if result.get('direct'):
            same_vertex = 'vertex' in source and source == target
            assert not result['steps'] and result['ticks'] == (0 if same_vertex else direct)
            return
        total, previous = 0, None
        for n, step in enumerate(result['steps']):
            i, kind, ticks = step['arc'], step['kind'], step['ticks']
            if previous is None:
                if 'vertex' in source:
                    assert self.arcs[i]['tail'] == source['vertex']
                else:
                    assert kind == 'suffix' and any(p['arc'] == i and p['ticks'] == ticks for p in source['partials'])
            else:
                delay = self.delay(previous, i)
                assert delay is not None
                total += delay
            if kind == 'full':
                assert ticks == (self.arcs[i]['ms']+124)//125
            elif kind == 'suffix':
                assert n == 0 and any(p['arc'] == i and p['ticks'] == ticks for p in source['partials'])
            elif kind == 'prefix':
                assert n == len(result['steps'])-1 and any(p['arc'] == i and p['ticks'] == ticks for p in target['partials'])
            else:
                raise ValueError('Captured path step kind')
            total += ticks
            previous = i
        assert previous is not None
        if 'vertex' in target:
            assert self.arcs[previous]['head'] == target['vertex']
        else:
            assert result['steps'][-1]['kind'] == 'prefix'
        assert total == result['ticks']
