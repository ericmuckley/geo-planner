"""Interpret sealed census counts without source access or graph construction."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
receipt=json.loads((HERE/'raw-run-v1/receipt.json').read_bytes())
bounds=json.loads((HERE/'raw-run-v1/bounds.json').read_bytes())
limit=162238546;rows={}
for name,bound in bounds.items():
    c=bound['counts'];ways=c['ways'];primitive=c['primitiveEdges']
    # Every nonempty source way retains its two ends, hence at least one edge.
    # At least one native node/anchor exists when ways>0. These intentionally
    # loose lower bounds do not rely on regional ratios or coordinate guesses.
    routing_low=24*ways+(16 if ways else 4)
    geometry_low=4*primitive+8*ways+(12 if ways else 4)
    rows[name]={'ways':ways,'deliveredReferences':c['references'],'primitiveEdges':primitive,
        'routingArrayLowerBytes':routing_low,'fullGeometryArrayLowerBytes':geometry_low,
        'combinedArrayLowerBytes':routing_low+geometry_low,
        'combinedArrayUpperBytes':bound['routingAndGeometryUpperBytes'],
        'wholeAcquiredFileFullGeometryFormatExceedsDecodedBudgetByLowerBound':routing_low+geometry_low>limit,
        'scope':'Current isolated full-geometry prototype arrays for the entire acquired publisher file. Other formats and continental-only subsets are not rejected by this bound.'}
t=receipt['histogram']['totals'];major=bounds['major-roads']['counts'];r=major['references'];members=t['relationNodeMembers']+t['relationWayMembers']
spools=24*r+8*t['taggedNodes']+16*members
result={'status':'count_based_interpretation_no_graph_admission','profiles':rows,'decodedAppBudgetBytes':limit,
    'exactTopologyCensusDesignBudget':{'selectedProfile':'major-roads','referenceOccurrenceRecordBytes':24,
        'sortedOccurrenceBytes':24*r,'taggedNodeIdBytes':8*t['taggedNodes'],
        'relationNodeAndWayStreamsIncludingSortedCopyBytes':16*members,
        'totalConservativeSpoolBytes':spools,
        'sourceNodePresenceBitsetBytes':(receipt['maxNodeId']+8)//8,
        'scope':'Design arithmetic only, not actual allocation/performance. Source-node presence can use a native one-bit-per-ID arena, with a fixed measured source max-ID resource bound; tagged/relation context streams remain separate.'},
    'allHighwayLongWays':sum(row['longWays'] for row in receipt['histogram']['highwayRoles'].values()),
    'wholeFileNotExactContinentalSubset':True,'compressedFunctionSizeMeasured':False,'etaQualified':False,'modelChanged':False}
if '--record' in sys.argv:
    with (HERE/'interpretation-v1.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(result,indent=2))
