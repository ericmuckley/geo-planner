"""Narrow road-level eligibility for an explicit ordinary-car lane, offline only.

All relevant access vectors must explicitly say yes at a common lane. No empty
inheritance, mode override, conditional or two-way lane assignment is inferred.
Existing road-level turns stay; this is not lane-to-lane routing.
"""
from coarse_osm_car_conditional_speed_v1 import POLICY as BASE_POLICY
from coarse_osm_car_conditional_speed_v1 import node_policy, restriction_policy
from coarse_osm_car_conditional_speed_v1 import way_policy as base_way_policy

LANE_KEYS=frozenset({'access:lanes','vehicle:lanes','motor_vehicle:lanes','motorcar:lanes'})
TOKENS=frozenset({'yes','no','designated','psv'})
HOV_TOKENS=frozenset({'yes','no','designated'})
POLICY=BASE_POLICY|{'id':'static-car-explicit-ordinary-lane-prototype-v1',
    'laneEligibility':'Only previously lane-access-rejected ways,static one-way direction,canonical1..32lane count,all nondirectional car-access vectors same length/known nonempty tokens,and a common explicitly yes lane. If HOV vector is present,that same lane must explicitly say yes. Whole-way restricted HOV,unknown forms,blank inheritance,other lane/direction/restriction constraints retain fallback. Source direction/speed/default/base access and all old positive decisions unchanged.',
    'laneScope':'Road-level ordinary-car eligibility only;no lane-change/turn/connectivity simulation or speed adjustment. Source lane/destination/change tags are retained,not rewritten.'}


def vector(text,count,tokens=TOKENS):
    if not isinstance(text,str) or len(text)>4096:return None
    values=tuple(text.split('|'))
    if len(values)!=count or any(value not in tokens for value in values):return None
    return values


def classify_way(tags):
    original=base_way_policy(tags)
    result={'policy':original,'explicitOrdinaryLaneIndices':(), 'acceptedLaneKeys':(), 'laneStatus':'unchanged'}
    if original.reason!='lane-access':return result
    keys=tuple(sorted(LANE_KEYS.intersection(tags)))
    count_text=tags.get('lanes','')
    if not isinstance(count_text,str) or not 1<=len(count_text)<=2 or not count_text.isascii() or not count_text.isdecimal() or str(int(count_text))!=count_text:return result
    count=int(count_text)
    if not 1<=count<=32 or not keys:return result
    oneway=tags.get('oneway:motorcar',tags.get('oneway:motor_vehicle',tags.get('oneway')))
    if oneway is None:oneway='yes' if tags.get('junction') in {'roundabout','circular'} or tags.get('highway')=='motorway' else 'no'
    if oneway not in {'yes','1','true','-1'} or tags.get('hov','yes')!='yes':return result
    if any(key in tags for key in ('lanes:forward','lanes:backward','lanes:both_ways','lanes:reversible')):return result
    if any(key.startswith('oneway:') and key not in {'oneway:motorcar','oneway:motor_vehicle'} for key in tags):return result
    if 'hov:minimum' in tags and 'hov:lanes' not in tags:return result
    columns=[vector(tags[key],count) for key in keys]
    if 'hov:lanes' in tags:columns.append(vector(tags['hov:lanes'],count,HOV_TOKENS))
    if any(values is None for values in columns):return result
    # Scope only canonical HOV lane syntax; unknown directional or conditional
    # HOV constraints must not be hidden by the general car-lane proof.
    if any(key.startswith('hov:') and key not in {'hov:lanes','hov:minimum'} for key in tags):return result
    ordinary=tuple(i for i in range(count) if all(values[i]=='yes' for values in columns))
    if not ordinary:return result
    scoped={key:value for key,value in tags.items() if key not in keys}
    proposed=base_way_policy(scoped)
    if proposed.reason is not None:return result
    if oneway=='-1':
        if proposed.forward is not None or proposed.backward is None:return result
    elif proposed.forward is None or proposed.backward is not None:return result
    return {'policy':proposed,'explicitOrdinaryLaneIndices':ordinary,'acceptedLaneKeys':keys,'laneStatus':'explicit-unrestricted-one-way-lane'}


def way_policy(tags):return classify_way(tags)['policy']
