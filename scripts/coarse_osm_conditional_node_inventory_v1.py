"""A converted relation never removes another source closure contributor."""
from coarse_timing_input import require


def closure_unions(relations,converted):
    original=set();remaining=set();seen=set()
    for row in relations:
        identity=row['sourceRelation']
        require(type(identity) is int and identity>0 and identity not in seen,'Unique original closing relation IDs')
        seen.add(identity)
        ways={int(value) for value in row['closedWays']}
        require(ways and all(value>0 for value in ways),'Complete original member-way closures')
        original.update(ways)
        if identity not in converted:remaining.update(ways)
    require(converted<=seen,'Every candidate belongs to an original closing contributor')
    return original,remaining
