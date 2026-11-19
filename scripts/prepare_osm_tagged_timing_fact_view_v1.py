"""Freeze native file-bind catalogs from small closed metadata only."""
import argparse
import hashlib
import json
from pathlib import Path
from coarse_osm_fact_view_v1 import compose

REPO=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan');parser.add_argument('pin');args=parser.parse_args()
    recipe=REPO/args.plan;assert sha(recipe)==args.pin;p=json.loads(recipe.read_bytes())
    assert p['output']=='docs/evidence/coarse-osm-car-capacity-2026-11-01/tagged-timing-fact-views-v1.json' and p['controls']==13
    assert set(p['sourcePairs'])=={'captured','country'}
    for name,pin in p['bindings'].items():assert sha(REPO/name)==pin,name
    views={}
    for label,pair in p['sourcePairs'].items():
        views[label]=compose(*(json.loads((REPO/pair[name]).read_bytes()) for name in ('base','overlay')))
    result={'format':'geo-planner-tagged-timing-fact-view-catalog-v1','recipeSha256':args.pin,'views':views,'sourcePairs':p['sourcePairs'],
            'originalLegalSpeedCatalog':p['originalLegalSpeedCatalog'],'originalLegalSpeedCatalogSha256':sha(REPO/p['originalLegalSpeedCatalog']),'derivedPolicy':p['policy'],'costFactsMeaning':'Derived estimated driving speeds/costs;original legal/default speed source remains separately pinned and unchanged.','actualFactFilesReadOrCopiedOrLinked':0,'nativeProgramsExecuted':0,'scope':'Closed-metadata-only complete-field file-bind catalogs. Ways/arcs/flags select overlay as whole groups, all other typed base fields retained; no stale tail, no source/graph/IO/performance/accuracy or app admission.'}
    raw=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<=1048576
    with (REPO/p['output']).open('xb') as stream:stream.write(raw)
    print(json.dumps({'views':{n:{'files':len(v['files']),'fields':v['fields']} for n,v in views.items()},'outputBytes':len(raw)}))


if __name__=='__main__':main()
