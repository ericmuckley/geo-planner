"""Road-only static-car prototype policy; source tags remain unchanged offline."""
from dataclasses import dataclass

from import_roads import DEFAULT_SPEEDS,TURN_KINDS,access_allowed,speed_kph
from barrier_policy import barrier_decision
from coarse_osm_backbone_v1 import MAJOR
from coarse_timing_input import require

POLICY={'id':'native-road-only-static-car-prototype-v1','roles':list(MAJOR),
        'defaultSpeedsKph':{role:DEFAULT_SPEEDS[role] for role in MAJOR},
        'signalDelayMs':5000,'uTurnDelayMs':20000,'tickMs':125,
        'ferries':'excluded','conditional':'conservative closure; no date/time evaluation',
        'viaWay':'conservative member-way closure in this first cost prototype',
        'uTurns':'Exact reverse physical arc only; permitted at source-way ends, selected-profile junctions, tagged or explicit relation nodes. Validation-window cuts never grant reversal permission.',
        'scope':'Assumed static travel costs and limited OSM car rules; no traffic, current availability, vehicle dimensions or nationwide ETA/coverage certification.'}


@dataclass(frozen=True)
class WayPolicy:
    reason:str|None
    forward:float|None=None
    backward:float|None=None
    forward_default:bool=False
    backward_default:bool=False


def way_policy(props):
    role=props.get('highway')
    if role not in MAJOR:return WayPolicy('outside-major-profile')
    if props.get('route')=='ferry' or props.get('ferry') not in (None,'no','false','0'):return WayPolicy('vehicle-ferry')
    if not access_allowed(props):return WayPolicy('access')
    if props.get('area')=='yes' or props.get('ford') or props.get('service') in {'driveway','parking_aisle'}:return WayPolicy('area-ford-driveway-parking')
    if any(k.endswith(':conditional') or k.startswith(('reversible','restriction')) for k in props):return WayPolicy('conditional-or-way-restriction')
    if any(k.endswith(':lanes') or ':lanes:' in k for k in props if k.startswith(('access','vehicle','motor','oneway'))):return WayPolicy('lane-access')
    oneway=props.get('oneway:motorcar',props.get('oneway:motor_vehicle',props.get('oneway')))
    if oneway is None:oneway='yes' if props.get('junction') in {'roundabout','circular'} or role=='motorway' else 'no'
    if oneway not in {'yes','1','true','no','0','false','-1'}:return WayPolicy('unsupported-oneway')
    f=props.get('maxspeed:forward',props.get('maxspeed'));b=props.get('maxspeed:backward',props.get('maxspeed'))
    try:forward=speed_kph(f,DEFAULT_SPEEDS[role]);backward=speed_kph(b,DEFAULT_SPEEDS[role])
    except ValueError:return WayPolicy('unsupported-speed')
    forward=forward if oneway!='-1' and access_allowed(props,'forward') else None
    backward=backward if oneway in {'no','0','false','-1'} and access_allowed(props,'backward') else None
    return WayPolicy('directional-access' if forward is None and backward is None else None,forward,backward,f is None,b is None)


def node_policy(props):
    blocked=not access_allowed(props) or any(k.endswith(':conditional') for k in props)
    barrier=barrier_decision(props) if props.get('barrier') else None
    if barrier is not None and not barrier['open']:blocked=True
    return {'blocked':blocked,'signal':props.get('highway')=='traffic_signals','tagged':bool(props),'barrier':barrier}


def restriction_policy(element):
    props=element['tags'];typ=props.get('type','');members=element.get('members',[])
    ways=sorted({m['ref'] for m in members if m['type']=='way'});nodes=sorted({m['ref'] for m in members if m['type']=='node'})
    base={'id':element['id'],'memberWays':ways,'memberNodes':nodes,'sourceTags':props,'sourceMembers':members}
    if not typ.startswith('restriction'):return base|{'status':'unrelated'}
    exceptions={v.strip() for v in props.get('except','').split(';')}
    mode=typ.split(':',1)[1] if ':' in typ else None
    if exceptions.intersection({'motorcar','motor_vehicle','vehicle'}) or mode and mode not in {'motorcar','motor_vehicle','vehicle'}:return base|{'status':'non-car'}
    kind=next((props[k] for k in ('restriction:motorcar','restriction:motor_vehicle','restriction:vehicle','restriction') if k in props),None)
    car_conditionals={'restriction:conditional','restriction:motorcar:conditional','restriction:motor_vehicle:conditional','restriction:vehicle:conditional'}
    if kind is None and not car_conditionals.intersection(props) and any(k.startswith('restriction:') for k in props):return base|{'status':'non-car'}
    froms=[m['ref'] for m in members if m['role']=='from' and m['type']=='way'];tos=[m['ref'] for m in members if m['role']=='to' and m['type']=='way'];via=[m['ref'] for m in members if m['role']=='via' and m['type']=='node']
    supported=(kind in TURN_KINDS and not any(k.endswith(':conditional') for k in props) and len(froms)==len(tos)==len(via)==1 and len(members)==3 and (froms[0]!=tos[0] or kind.endswith(('u_turn','straight_on'))))
    if supported:return base|{'status':'via-node','kind':kind,'fromWay':froms[0],'toWay':tos[0],'via':via[0]}
    require(ways or nodes,'Car prototype cannot locate unsupported restriction')
    return base|{'status':'closed-unsupported','reason':'via-way' if any(m['role']=='via' and m['type']=='way' for m in members) else 'unsupported-or-conditional'}


def turn_allowed(incoming,outgoing,reverse,rules):
    only=[]
    for rule in rules:
        matches=outgoing==rule['toWay']
        if rule['fromWay']==rule['toWay']:matches=matches and (reverse if rule['kind'].endswith('u_turn') else not reverse)
        if rule['kind'].startswith('only_'):only.append(matches)
        elif matches:return False
    return not only or any(only)
