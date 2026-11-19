"""Current raw-tag eligibility and original stored reasons are separate facts."""
from dataclasses import asdict

from coarse_osm_car_explicit_lanes_v1 import classify_way
from coarse_timing_input import require


def way_cause(row,raw):
    identity=row['sourceWay']
    require(type(identity) is int and identity>0,'Source way identity')
    result={key:row[key] for key in ('sourceWay','storedSourceFlags','baseEligible','finalFallbackClosed')}
    result.update(rawWayKnown=raw is not None,currentRawPolicy=None,rawTags=None,laneStatus=None)
    if raw is None:return result
    require(raw['type']=='way' and raw['id']==identity and isinstance(raw['tags'],dict),'Exact cached way identity/tags')
    classified=classify_way(raw['tags']);policy=classified['policy']
    require((policy.reason is None)==row['baseEligible'],'Current raw source eligibility reconciles')
    result.update(currentRawPolicy=asdict(policy),rawTags=raw['tags'],laneStatus=classified['laneStatus'])
    return result
