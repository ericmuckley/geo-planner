"""Offline node-policy prototype for three documented vehicle-passable features."""
from coarse_osm_car_conditional_scope_v1 import node_policy as previous_node_policy
from import_roads import CAR_KEYS

PASSABLE_BARRIERS=frozenset({'cattle_grid','entrance','toll_booth'})
POLICY={'id':'static-car-passable-barrier-defaults-v1',
        'passableBarrierDefaults':sorted(PASSABLE_BARRIERS),
        'access':'Use source-documented feature defaults only when no explicit car/general access key is present. Preserve existing mode precedence and every denial/unknown value.',
        'guards':'Retain existing car/general/unknown conditionals, access qualifiers, dimensions, locks and opening hours. Gate/lift_gate/border_control/unknown features keep previous policy.',
        'independentRestrictions':'A base-node change never clears any independent node-only restriction contributor.',
        'costs':'No speed, price, signal, turn, reversal or barrier-delay change.',
        'scope':'Generic source-tag interpretation prototype only; not current availability, lawful-trip, nationwide accuracy or app admission.'}


def node_policy(tags):
    previous=previous_node_policy(tags)
    if not previous['blocked'] or tags.get('barrier') not in PASSABLE_BARRIERS:
        return previous
    # Reuse every existing guard through a recognized control-point shape.
    # This copy tests the documented default; original source tags stay intact.
    probe=tags|{'barrier':'toll_booth'}
    access_key=next((key for key in CAR_KEYS if key in tags),None)
    if access_key is None:
        probe['motorcar']='yes'
    guarded=previous_node_policy(probe)
    if guarded['blocked']:
        return previous
    barrier={'open':True,'accessKey':access_key,'accessValue':tags.get(access_key),
             'reason':'documented-passable-barrier-default' if access_key is None else 'explicit-car-permission'}
    return previous|{'blocked':False,'barrier':barrier}


def graph_node_decision(tags,restriction_contributors):
    base=node_policy(tags)
    return {'base':base,'blocked':base['blocked'] or bool(restriction_contributors)}
