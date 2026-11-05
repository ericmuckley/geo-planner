"""Static lower speed envelope for supported conditional limits, offline only.

Conditions are opaque and never evaluated. Taking the minimum of every stated
positive numeric limit and the base speed bounds all possible condition states.
Other constraints, unparseable values and unsupported syntax keep legacy closure.
"""
from dataclasses import replace
from import_roads import speed_kph
import coarse_osm_car_conditional_scope_v1 as scope
from coarse_osm_car_conditional_scope_v1 import ignored_keys,node_policy,restriction_policy

SPEED_KEYS=('maxspeed:conditional','maxspeed:forward:conditional','maxspeed:backward:conditional')
POLICY=scope.POLICY|{
    'id':'native-road-only-static-car-conditional-speed-prototype-v1',
    'conditionalSpeed':'For supported numeric general/forward/backward maxspeed conditionals only, take min(base,all common limits,all matching-direction limits). No departure/condition evaluation; unsupported syntax/values and other constraints remain closed. Previously eligible ways retain their exact costs/directions.',
}


def conditional_speeds(text):
    if not isinstance(text,str) or not text or len(text)>65536:return None
    depth=0;start=0;clauses=[]
    for index,char in enumerate(text):
        if char in ('"',"'"):return None
        if char=='(':
            depth+=1
            if depth>8:return None
        elif char==')':
            depth-=1
            if depth<0:return None
        elif char==';' and depth==0:
            clauses.append(text[start:index]);start=index+1
            if len(clauses)>=64:return None
    if depth:return None
    clauses.append(text[start:]);values=[]
    for clause in clauses:
        if clause.count('@')!=1:return None
        value,condition=(part.strip() for part in clause.split('@',1))
        if not condition.replace('(','').replace(')','').strip():return None
        try:speed=speed_kph(value,None)
        except ValueError:return None
        if speed is None:return None
        values.append(speed)
    return tuple(values)


def classify_way(tags):
    original=scope.way_policy(tags);present=tuple(key for key in SPEED_KEYS if key in tags)
    explanation={'policy':original,'ignoredNonCarKeys':ignored_keys(tags),'candidateSpeedKeys':present,'staticallyPricedSpeedKeys':(),
                 'conditionalSpeedStatus':'absent' if not present else 'unsupported','conditionalSpeedValues':{}}
    if not present:return explanation
    parsed={key:conditional_speeds(tags[key]) for key in present}
    if any(values is None for values in parsed.values()):return explanation
    base=scope.way_policy({key:value for key,value in tags.items() if key not in SPEED_KEYS})
    if base.reason is not None:return explanation|{'conditionalSpeedStatus':'blocked-by-other-policy'}
    common=parsed.get('maxspeed:conditional',())
    def direction(speed,default,key):
        if speed is None:return speed,default
        chosen=min((speed,*common,*parsed.get(key,())))
        return chosen,default and chosen>=speed
    forward,forward_default=direction(base.forward,base.forward_default,'maxspeed:forward:conditional')
    backward,backward_default=direction(base.backward,base.backward_default,'maxspeed:backward:conditional')
    return explanation|{'policy':replace(base,forward=forward,backward=backward,forward_default=forward_default,backward_default=backward_default),
                        'staticallyPricedSpeedKeys':present,'conditionalSpeedStatus':'static-minimum','conditionalSpeedValues':parsed}


def way_policy(tags):
    return classify_way(tags)['policy']
