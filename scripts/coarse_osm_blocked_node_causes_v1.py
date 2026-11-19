"""Explain stored blocking evidence without removing any contribution."""
from coarse_osm_car_conditional_scope_v1 import node_policy


def node_cause(identity, flags, raw, contributors):
    assert type(identity) is int and identity > 0 and 0 <= flags < 8 and flags & 1
    assert all(type(value) is int and value > 0 for value in contributors)
    result = {'sourceNodeId':str(identity),'graphFlags':flags,
              'restrictionContributorIds':sorted(set(contributors)),
              'rawNodeKnown':raw is not None,'rawBaseBlocked':None,
              'sourceBlockingReconciled':None,'sourceSignalReconciled':None,
              'cause':'raw-node-unknown'}
    if raw is None:
        return result
    assert raw['type'] == 'node' and type(raw['id']) is int and raw['id'] == identity
    tags = raw['tags']
    assert isinstance(tags,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in tags.items())
    decision = node_policy(tags)
    base = decision['blocked']
    result.update(rawTags=tags,rawBaseDecision=decision,rawBaseBlocked=base,
                  sourceBlockingReconciled=bool(flags & 1)==(base or bool(contributors)),
                  sourceSignalReconciled=bool(flags & 2)==decision['signal'])
    result['cause'] = ('base-and-restriction' if contributors else 'base-node') if base else ('restriction-only' if contributors else 'unexplained-stored-block')
    return result
