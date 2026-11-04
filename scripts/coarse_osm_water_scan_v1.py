"""One fully bound water census; source validation and water lifecycle stay separate."""
from coarse_timing_input import require


def collect(engine, source_path, snapshot, caps, source, expected_counts, expected_semantic, check):
    engine.begin()
    try:
        receipt = engine.scan(source_path, snapshot, caps, source=source, check=check)
        require(receipt['nativeEof'] and receipt['counts'] == expected_counts, 'Water complete source counts')
        require(receipt['semanticSha256'] == expected_semantic, 'Water inherited complete source semantic identity')
        require(receipt['pythonProjectionFrames'] == 0, 'Water has no Python source object projections')
        counters = engine.finish()
        require({k: counters[k+'s'] for k in expected_counts} == expected_counts, 'Water consumer full-source count identity')
        return {'receipt': receipt, 'water': counters}
    finally:
        engine.release()
