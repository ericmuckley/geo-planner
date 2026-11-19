"""Conservative static envelope for a single supported conditional via-node ban."""
from dataclasses import dataclass

from coarse_osm_car_policy_v1 import restriction_policy

KINDS=frozenset({'no_left_turn','no_right_turn','no_straight_on','no_u_turn'})
BASE_KEYS=('restriction:motorcar','restriction:motor_vehicle','restriction:vehicle','restriction')
CONDITIONAL_KEYS=frozenset(key+':conditional' for key in BASE_KEYS)
NON_CAR_EXCEPTIONS=frozenset({'foot','bicycle','hgv','psv','bus','motorcycle','emergency','agricultural','forestry','goods'})
POLICY={'id':'static-car-conditional-via-node-prohibitory-envelope-v1',
        'shape':'Exactly one from way, one via node and one distinct to way; positive native IDs; original car policy must classify closed-unsupported.',
        'values':sorted(KINDS),
        'scope':'At least one known car/general conditional key. All stated car/general base and conditional values must be the same supported prohibitory kind. Conditions remain opaque; the maneuver stays banned in every state.',
        'syntax':'At most 65536 Unicode characters per conditional value, 64 top-level clauses and eight parenthesis levels; exactly one @ per clause, nonempty condition, no quotes. Unknown/malformed syntax or keys retain fallback.',
        'fallback':'Only-turns, via ways, same-way turns, unknown restriction/conditional keys and unknown/car exemptions keep the complete original fallback. Every independent contributor remains.',
        'unchanged':'No condition/departure-time evaluation, speed/cost/direction/access/node-barrier change, selected-place exception or routing/app admission.'}


@dataclass(frozen=True)
class ConditionalNodeTurn:
    identity:int
    from_way:int
    via_node:int
    to_way:int
    kind:str


def conditional_values(text):
    if not isinstance(text,str) or not 0<len(text)<=65536 or any(c in text for c in ('\"',"'")):
        return None
    clauses=[];depth=start=0
    for index,char in enumerate(text):
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
        value,condition=clause.split('@')
        value=value.strip()
        if value not in KINDS or not any(not c.isspace() and c not in '()' for c in condition):return None
        values.append(value)
    return tuple(values)


def classify(element):
    def refused(reason):return {'rule':None,'reason':reason}
    if not isinstance(element,dict) or type(element.get('id')) is not int or not 0<element['id']<2**63:
        return refused('invalid-identity')
    tags=element.get('tags');members=element.get('members')
    if not isinstance(tags,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in tags.items()):
        return refused('invalid-tags')
    if not isinstance(members,list) or len(members)!=3:
        return refused('unsupported-member-shape')
    grouped={}
    for member in members:
        if not isinstance(member,dict):return refused('unsupported-member-shape')
        role=member.get('role');kind=member.get('type');identity=member.get('ref')
        if role not in ('from','via','to') or role in grouped or kind!=('node' if role=='via' else 'way') or type(identity) is not int or not 0<identity<2**63:
            return refused('unsupported-member-shape')
        grouped[role]=identity
    if grouped['from']==grouped['to']:return refused('same-way-fallback')
    original=restriction_policy(element)
    if original['status']!='closed-unsupported':return refused('not-original-car-fallback')
    if any(k.startswith('restriction:') and k not in (*BASE_KEYS,*CONDITIONAL_KEYS) for k in tags):
        return refused('unknown-restriction-key')
    if any(k.endswith(':conditional') and k not in CONDITIONAL_KEYS for k in tags):
        return refused('unknown-conditional-key')
    if 'except' in tags and not {v.strip() for v in tags['except'].split(';')}<=NON_CAR_EXCEPTIONS:
        return refused('unknown-or-car-exemption')
    keys=CONDITIONAL_KEYS.intersection(tags)
    if not keys:return refused('no-car-condition')
    values=[tags[key] for key in BASE_KEYS if key in tags]
    for key in sorted(keys):
        parsed=conditional_values(tags[key])
        if parsed is None:return refused('unsupported-conditional-syntax')
        values.extend(parsed)
    if not values or len(set(values))!=1 or values[0] not in KINDS:
        return refused('unsupported-or-mixed-kind')
    kind=values[0]
    # The unchanged static oracle must represent exactly the derived maneuver.
    static_tags={k:v for k,v in tags.items() if k not in CONDITIONAL_KEYS}
    static_tags['restriction']=kind
    static=restriction_policy(element|{'tags':static_tags})
    if static['status']!='via-node':return refused('static-oracle-fallback')
    assert (static['fromWay'],static['via'],static['toWay'],static['kind'])==(grouped['from'],grouped['via'],grouped['to'],kind)
    return {'rule':ConditionalNodeTurn(element['id'],grouped['from'],grouped['via'],grouped['to'],kind),
            'reason':'single-prohibitory-via-node-all-condition-envelope'}
