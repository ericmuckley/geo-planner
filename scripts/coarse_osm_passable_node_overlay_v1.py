"""Derive node-only flags from complete original tag evidence; all other bytes stay exact."""
from coarse_osm_blocked_node_causes_v1 import node_cause
from coarse_osm_car_passable_barriers_v1 import graph_node_decision
from coarse_timing_input import require


def validate_inputs(flags,mapping,evidence):
    require(isinstance(flags,bytes) and flags and all(value<8 for value in flags),'Complete bounded source node flags')
    by_vertex={row['vertex']:row for row in mapping}
    require(len(by_vertex)==len(mapping)==len(evidence),'Unique complete blocked-node mapping/tag roster')
    require(set(by_vertex)=={i for i,value in enumerate(flags) if value&1},'ALL current blocked vertices and no unblocked vertices')
    require({str(row['sourceNodeId']) for row in mapping}==set(evidence),'Every blocked native ID has original tags')
    for vertex,row in by_vertex.items():
        require(type(vertex) is int and 0<=vertex<len(flags) and row['flags']==flags[vertex],'Exact source flag/mapping tuple')
        identity=str(row['sourceNodeId']);original=evidence[identity]
        reproduced=node_cause(int(identity),row['flags'],{'type':'node','id':int(identity),'tags':original['rawTags']},original['restrictionContributorIds'])
        require(reproduced==original and reproduced['sourceBlockingReconciled'] and reproduced['sourceSignalReconciled'],'Complete original base/restriction/signal evidence replay')
    return by_vertex


def build_overlay(flags,mapping,evidence):
    by_vertex=validate_inputs(flags,mapping,evidence)
    output=bytearray(flags);changed=[]
    for vertex,row in sorted(by_vertex.items()):
        identity=str(row['sourceNodeId']);original=evidence[identity]
        decision=graph_node_decision(original['rawTags'],original['restrictionContributorIds'])
        require(decision['base']['signal']==bool(flags[vertex]&2),'Signal policy unchanged')
        if not decision['blocked']:
            require(not original['restrictionContributorIds'],'Never clear independent node-only contributors')
            output[vertex]&=~1
            changed.append({'vertex':vertex,'sourceNodeId':identity,'oldFlags':flags[vertex],
                            'newFlags':output[vertex],'rawTags':original['rawTags'],
                            'newBaseDecision':decision['base']})
    return bytes(output),changed


def audit_overlay(original,proposed,mapping,evidence):
    by_vertex=validate_inputs(original,mapping,evidence)
    require(isinstance(proposed,bytes) and len(original)==len(proposed),'Overlay exact graph shape')
    changed=[]
    for vertex,(before,after) in enumerate(zip(original,proposed)):
        expected=before
        if before&1:
            row=by_vertex[vertex];source=evidence[str(row['sourceNodeId'])]
            decision=graph_node_decision(source['rawTags'],source['restrictionContributorIds'])
            if not decision['blocked']:expected=before&~1
        require(after==expected,'Every proposed node flag independently replays')
        if before!=after:changed.append(vertex)
    return {'allVertexFlagsIndependentlyCompared':len(original),'originalBlockedVertices':len(mapping),
            'changedVertices':changed,'remainingBlockedVertices':len(mapping)-len(changed),
            'signalsAndReversalBitsExact':all((a&6)==(b&6) for a,b in zip(original,proposed)),
            'everyIndependentRestrictionContributorRetained':True,
            'everyOldUnblockedVertexExact':True}
