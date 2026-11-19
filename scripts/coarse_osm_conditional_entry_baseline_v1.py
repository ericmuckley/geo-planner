"""Derive the old-closure post count from the audited source insertion ledger."""
from bisect import bisect_left


def baseline(ways,closures,insertions,old_pre,old_post,new_pre):
    assert 0<old_post<=old_pre<=new_pre<=0xffffff and len(ways)<=8000000 and len(closures)<=200000
    total=retained=groups=0;previous_way=-1;previous_at=0
    for way,old_at,new_first,count in insertions:
        assert previous_way<way<len(ways) and previous_at<=old_at<=old_pre and new_first==old_at+total and 0<count<=1000000
        previous_way,previous_at=way,old_at;groups+=1;assert groups<=250000
        identity=ways[way][0];assert identity>0
        at=bisect_left(closures,identity)
        if at==len(closures) or closures[at]!=identity:retained+=count
        total+=count;assert total<=1000000
    assert old_pre+total==new_pre
    return {'originalPostArcs':old_post,'addedPreClosureArcs':total,'addedArcsOutsideOriginalClosures':retained,
            'addedArcsInsideOriginalClosures':total-retained,'newPostUnderOriginalClosures':old_post+retained,'insertionGroups':groups}
