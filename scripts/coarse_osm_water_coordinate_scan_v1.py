"""One protected coordinate capture; source and coordinate lifecycles stay separate."""
from coarse_timing_input import require


def collect(engine,path,snapshot,caps,source,expected_counts,expected_semantic,check):
    engine.begin()
    try:
        receipt=engine.scan(path,snapshot,caps,source=source,check=check)
        require(receipt['nativeEof'] and receipt['counts']==expected_counts,'Water coordinate complete source counts')
        require(receipt['semanticSha256']==expected_semantic and receipt['pythonProjectionFrames']==0,'Water coordinate complete source semantic identity/no Python projections')
        measured=engine.finish()
        require(measured['capture']['requested']==engine.requested and measured['capture']['complete']==1,'Water coordinate complete requested-ID capture')
        return {'receipt':receipt,'coordinates':measured}
    finally:engine.release()
