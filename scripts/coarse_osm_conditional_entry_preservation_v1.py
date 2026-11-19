"""Prove new entry closures/pairs retain every old allowed source transition."""
from bisect import bisect_right


class ArcMap:
    def __init__(self,insertions,old_count,new_count):
        self.old_count,self.new_count=old_count,new_count;self.old=[];self.first=[];self.end=[];self.total=[0]
        prior_way=-1;prior_at=0
        for way,old_at,new_first,count in insertions:
            assert way>prior_way and prior_at<=old_at<=old_count and new_first==old_at+self.total[-1] and count>0
            prior_way,prior_at=way,old_at;self.old.append(old_at);self.first.append(new_first);self.end.append(new_first+count);self.total.append(self.total[-1]+count)
        assert old_count+self.total[-1]==new_count and len(self.old)<=250000
    def forward(self,old):
        assert 0<=old<self.old_count
        return old+self.total[bisect_right(self.old,old)]
    def backward(self,new):
        assert 0<=new<self.new_count
        at=bisect_right(self.first,new)-1
        if at>=0 and new<self.end[at]:return None
        return new-self.total[bisect_right(self.end,new)]


def audit(old_closed,new_closed,old_pairs,new_pairs,insertions,old_count,new_count,way_of_new_arc):
    old_closed,new_closed=set(old_closed),set(new_closed);assert new_closed<=old_closed
    assert len(old_closed)<=200000
    mapping=ArcMap(insertions,old_count,new_count);old_pairs=set(old_pairs);new_pairs=set(new_pairs)
    assert len(old_pairs)<=2000000 and len(new_pairs)<=2000000
    retained={(mapping.forward(a),mapping.forward(b)) for a,b in old_pairs};assert retained<=new_pairs
    old_active_pairs=added_touching_new=added_touching_closed=0
    for a,b in new_pairs:
        left,right=mapping.backward(a),mapping.backward(b)
        if left is None or right is None:added_touching_new+=1;continue
        if way_of_new_arc(a) in old_closed or way_of_new_arc(b) in old_closed:added_touching_closed+=1;continue
        assert (left,right) in old_pairs,'New restriction cannot close an old active source transition'
        old_active_pairs+=1
    return {'oldClosureIds':len(old_closed),'newClosureIds':len(new_closed),'allNewClosuresAreOldClosures':True,
            'oldEntryPairsRetained':len(retained),'newEntryPairs':len(new_pairs),'pairsOnOldActiveArcs':old_active_pairs,
            'pairsTouchingNewArcs':added_touching_new,'pairsTouchingOldClosedWays':added_touching_closed,'allOldAllowedSourceTransitionsRetained':True}
