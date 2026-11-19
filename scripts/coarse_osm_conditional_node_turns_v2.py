"""Explicit source relation-type guard around the sealed V1 conditional envelope."""
from coarse_osm_conditional_node_turns_v1 import BASE_KEYS,CONDITIONAL_KEYS,KINDS,ConditionalNodeTurn,conditional_values
from coarse_osm_conditional_node_turns_v1 import POLICY as PREVIOUS_POLICY
from coarse_osm_conditional_node_turns_v1 import classify as previous_classify

TYPES=('restriction','restriction:motorcar','restriction:motor_vehicle','restriction:vehicle')
POLICY=PREVIOUS_POLICY|{'id':'static-car-conditional-via-node-prohibitory-envelope-v2',
                      'relationTypes':list(TYPES),
                      'typeGuard':'Only exact documented general/car relation types. Unknown restriction-prefixed types retain original fallback; the sealed baseline oracle intentionally treats them conservatively.'}


def classify(element):
    if isinstance(element,dict) and isinstance(element.get('tags'),dict) and element['tags'].get('type') not in TYPES:
        return {'rule':None,'reason':'unsupported-relation-type'}
    return previous_classify(element)
