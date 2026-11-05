"""Read captured source tags only; compare classifiers without building a graph."""
from array import array
from collections import Counter
from dataclasses import asdict
import json
import sqlite3
import sys

from coarse_osm_backbone_v1 import MAJOR
import coarse_osm_car_policy_v2 as old
import coarse_osm_car_conditional_speed_v1 as new
from inventory_osm_car_conditional_scope_v1 import selected_ordinals


def inventory(database,selected,expected,emit,check=lambda:None):
    assert 0<=expected['node']<=2000000 and 0<=expected['way']<=500000
    assert len(selected)<=200000 and all(0<=index<expected['node'] for index in selected)
    assert all(a<b for a,b in zip(selected,selected[1:]))
    db=sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
    counts=Counter({key:0 for key in ['nodeNewPositive','wayNewPositive','nodeWithIgnoredConditionalKeys','wayWithIgnoredConditionalKeys','wayWithConditionalCandidates','wayStaticSpeedPriced','waySpeedUnsupported','nodeOldPositiveRetained','wayOldPositiveRetained']});keys=Counter();ignored_counts=Counter();speed_counts=Counter()
    def classify(kind,identity,encoded):
        assert isinstance(encoded,str) and len(encoded.encode('utf8'))<=4194304
        tags=json.loads(encoded);assert isinstance(tags,dict) and len(tags)<=65536
        assert all(isinstance(k,str) and isinstance(v,str) and len(k.encode('utf8'))<=1024 for k,v in tags.items())
        for key in tags:
            if key.endswith(':conditional'):keys[kind+'/'+key]+=1
        assert len(keys)<=5000
        ignore=new.ignored_keys(tags)
        if kind=='node':
            before={k:v for k,v in old.node_policy(tags).items() if k in ('blocked','signal','tagged')}
            after={k:v for k,v in new.node_policy(tags).items() if k in ('blocked','signal','tagged')}
            positive=not before['blocked'];gained=before['blocked'] and not after['blocked']
            counts['selectedNodeTagged']+=int(before['tagged']);counts['selectedNodeSignals']+=int(before['signal'])
            counts['selectedNodeBlockedBefore']+=int(before['blocked']);counts['selectedNodeBlockedAfter']+=int(after['blocked'])
        else:
            explanation=new.classify_way(tags)
            before=asdict(old.way_policy(tags));after=asdict(explanation['policy'])
            counts['waySpeedStatus/'+explanation['conditionalSpeedStatus']]+=1
            if explanation['staticallyPricedSpeedKeys']:
                counts['wayStaticSpeedPriced']+=1
                for key in explanation['staticallyPricedSpeedKeys']:speed_counts[key]+=1
            if explanation['candidateSpeedKeys'] and explanation['conditionalSpeedStatus']=='unsupported':counts['waySpeedUnsupported']+=1
            positive=before['reason'] is None;gained=not positive and after['reason'] is None
            counts['wayReasonBefore/'+str(before['reason'])]+=1;counts['wayReasonAfter/'+str(after['reason'])]+=1
        counts[kind+'MetadataClassified']+=1
        if positive:assert after==before;counts[kind+'OldPositiveRetained']+=1
        if not ignore and not (kind=='way' and explanation['staticallyPricedSpeedKeys']):assert after==before
        if gained:counts[kind+'NewPositive']+=1
        if ignore:
            counts[kind+'WithIgnoredConditionalKeys']+=1
            for key in ignore:ignored_counts[kind+'/'+key]+=1
        details={key:value for key,value in explanation.items() if key!='policy'} if kind=='way' else {'ignoredNonCarKeys':ignore,'candidateSpeedKeys':(),'staticallyPricedSpeedKeys':(),'conditionalSpeedStatus':'not-a-way','conditionalSpeedValues':{}}
        if ignore or details['candidateSpeedKeys']:
            if kind=='way':counts['wayWithConditionalCandidates']+=1
            emit({'kind':kind,'id':identity,**details,'tags':tags,'before':before,'after':after,'eligibilityGained':gained})
    try:
        node_count=0;cursor=0;previous=0
        for ordinal,(identity,encoded) in enumerate(db.execute("SELECT id,json_extract(CAST(raw AS TEXT),'$.tags') FROM objects WHERE kind='node' ORDER BY id")):
            assert identity>previous;previous=identity;node_count+=1
            if ordinal%8192==0:check()
            if cursor<len(selected) and ordinal==selected[cursor]:classify('node',identity,encoded);cursor+=1
        assert node_count==expected['node'] and cursor==len(selected)
        counts['capturedNodeRowsVisited']=node_count
        ways=db.execute("SELECT count(*) FROM objects WHERE kind='way'").fetchone()[0];assert ways==expected['way'];counts['capturedWayRows']=ways
        query="SELECT id,json_extract(CAST(raw AS TEXT),'$.tags') FROM objects WHERE kind='way' AND json_extract(CAST(raw AS TEXT),'$.tags.highway') IN ("+','.join('?' for _ in MAJOR)+") ORDER BY id"
        way_count=0;previous=0
        for identity,encoded in db.execute(query,MAJOR):
            assert identity>previous;previous=identity;way_count+=1
            if way_count%2048==0:check()
            classify('way',identity,encoded)
        assert way_count==expected['majorWays'];check()
    finally:db.close()
    return {'counts':dict(counts),'conditionalKeyCounts':dict(sorted(keys.items())),'ignoredKeyCounts':dict(sorted(ignored_counts.items())),'staticSpeedKeyCounts':dict(sorted(speed_counts.items()))}


