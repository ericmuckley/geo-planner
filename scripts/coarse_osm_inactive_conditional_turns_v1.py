"""Fixed-profile no-turn effects; absence is never a grant of source access."""
from collections import defaultdict
from dataclasses import asdict

from analyze_osm_source_gap_closures_v2 import contribution
from coarse_osm_conditional_node_facts_v1 import relation_overlay as previous_overlay
from coarse_osm_conditional_node_ports_v1 import audit as audit_ports
from coarse_osm_conditional_node_turns_v2 import classify
from coarse_timing_input import require

INACTIVE = frozenset({'from-way-outside-major-facts','to-way-outside-major-facts',
                      'from-way-base-ineligible','to-way-base-ineligible',
                      'no-directed-incoming-source-port','no-directed-outgoing-source-port'})
POLICY = {'id':'fixed-profile-inactive-conditional-node-ban-v1',
          'shape':'Unchanged qualified four-kind single-via-node prohibitory all-state envelope, distinct from/to ways.',
          'inactiveStatuses':sorted(INACTIVE),
          'scope':'No eligible directed from-via-to transition in the COMPLETE fixed source pre-arc profile. Keep represented bans and every independent closure/access/node constraint. Missing-via/unknown/complexity/only-turn forms keep fallback. Profile/source/pre-arcs changes invalidate the certificate. No permission, local-surrogate turn, timing-price or app admission claim.'}


def effects(metadata, descriptors):
    candidates={}
    for item in metadata:
        rule=classify(item['source'])['rule']
        require(rule is not None and rule.identity not in candidates,'Unique unchanged all-state source rule')
        require({k:str(v) if type(v) is int else v for k,v in asdict(rule).items()}==item['derived'],'Exact original derived source identities')
        candidates[rule.identity]=rule
    represented=set();inactive=set();fallback=set();seen=set()
    for row in descriptors:
        identity=int(row['sourceRelationId']);require(identity in candidates and identity not in seen,'Unique complete original port rows');seen.add(identity)
        rule=candidates[identity]
        require((row['fromWayId'],row['viaNodeId'],row['toWayId'],row['kind'])==(str(rule.from_way),str(rule.via_node),str(rule.to_way),rule.kind),'Exact source descriptor identity')
        incoming,outgoing=row['incomingPreArcIds'],row['outgoingPreArcIds']
        for ports in (incoming,outgoing):
            require(isinstance(ports,list) and ports==sorted(set(ports)) and all(type(i) is int and 0<=i<0xffffff for i in ports),'Canonical bounded source pre-arc IDs')
        status=row['status']
        if status=='source-ports-supported':
            require(incoming and outgoing,'Represented maneuver needs both ports');represented.add(identity)
        elif status in INACTIVE:
            if status=='from-way-outside-major-facts':require(row['fromWayRow'] is None and not incoming and not outgoing,'Absent from-profile member')
            elif status=='to-way-outside-major-facts':require(row['toWayRow'] is None and row['fromWayRow'] is not None and not incoming and not outgoing,'Absent to-profile member')
            elif status.endswith('base-ineligible'):require(row['fromWayRow'] is not None and row['toWayRow'] is not None and not incoming and not outgoing,'Ineligible member has no eligible source ports')
            else:
                require(all(type(row[k]) is int and row[k]>=0 for k in ('fromWayRow','toWayRow','viaSourceNodeIndex','viaAnchor')),'Negative directed-port proof requires known source junction')
                require(not (incoming if status=='no-directed-incoming-source-port' else outgoing),'No affected directed incidence')
            inactive.add(identity)
        else:fallback.add(identity)
    require(seen==candidates.keys(),'Every metadata rule retains a port outcome')
    return dict(represented=represented,inactive=inactive,fallback=fallback,rules=candidates)


def audit_effects(fields, metadata, port_result, check=lambda:None):
    result=effects(metadata,port_result['rows'])
    proof=audit_ports(fields,[result['rules'][i]for i in sorted(result['rules'])],port_result,check)
    return proof|dict(representedRules=len(result['represented']),inactiveRules=len(result['inactive']),fallbackRules=len(result['fallback']),
                      scope='Exact complete fixed pre-arc profile only; not source permission, local surrogate semantics or a different profile.')


def relation_overlay(elements,single,multi,old_closed,metadata,descriptors):
    require(isinstance(elements,(list,tuple)), 'Stable complete relation corpus for both audits')
    result=previous_overlay(elements,single,multi,old_closed,metadata,descriptors)
    classified=effects(metadata,descriptors);inactive=set();contributors=defaultdict(set)
    by_id={row['source']['id']:row['source']for row in metadata}
    for element in elements:
        ways,kind,branch=contribution(element,single,multi)
        identity=element['id']
        if identity in classified['inactive']:
            require(element==by_id[identity] and kind=='constant-conditional' and branch is None,'Only the exact qualified original contribution changes')
            rule=classified['rules'][identity]
            require(set(ways)=={rule.from_way,rule.to_way},'Complete original member-way contribution')
            inactive.add(identity)
        for way in ways:contributors[way].add(identity)
    converted=set(result['added'])|inactive
    original=set(contributors);proposed={way for way,ids in contributors.items()if ids-converted}
    require(original==set(old_closed) and proposed<=result['closed'],'Complete old/current/new closure unions')
    result.update(closed=proposed,convertedRelations=len(converted),inactiveRelations=inactive,
                  inactiveOutsideLocalMetadata=len(classified['inactive']-inactive),
                  reopenedWayIds=sorted(original-proposed),
                  sharedClosedWaysRetained=sum(bool(ids&converted)and bool(ids-converted)for ids in contributors.values()))
    return result
