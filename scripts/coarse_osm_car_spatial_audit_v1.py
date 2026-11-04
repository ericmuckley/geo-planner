"""Independent every-field spatial permutation audit; no native/producer/query."""
from array import array
from pathlib import Path
import time

from coarse_osm_car_spatial_reference_v1 import morton
from coarse_osm_car_packed_audit_v1 import FILES,unpack24


def audit(source,output):
    began=time.monotonic();source=Path(source);output=Path(output)
    assert {p.name for p in output.iterdir()}==FILES|{'cell-keys.u24','cell-offsets.u24','new-vertex-to-old.u32','old-arc-to-new.u32'}
    def raw(root,name):
        path=root/name;assert path.is_file() and not path.is_symlink() and path.stat().st_size<=67108864
        return path.read_bytes()
    def words(root,name,code):
        result=array(code);result.frombytes(raw(root,name));return result
    old_xy=words(source,'xy.i32','i');new_xy=words(output,'xy.i32','i')
    old_offsets=unpack24(raw(source,'offsets.u24'));new_offsets=unpack24(raw(output,'offsets.u24'))
    old_targets=unpack24(raw(source,'targets.u24'));new_targets=unpack24(raw(output,'targets.u24'))
    old_costs=words(source,'costs.u16','H');new_costs=words(output,'costs.u16','H')
    old_flags=raw(source,'node-flags.u8');new_flags=raw(output,'node-flags.u8')
    old_reverse=raw(source,'reverse.u8');new_reverse=raw(output,'reverse.u8')
    order=words(output,'new-vertex-to-old.u32','I');arc_map=words(output,'old-arc-to-new.u32','I')
    vertices=len(old_flags);arcs=len(old_targets)
    assert 0<vertices<=0xffffff and arcs<=0xffffff and len(order)==vertices and len(arc_map)==arcs
    assert len(old_xy)==len(new_xy)==2*vertices and len(new_flags)==vertices
    assert len(old_offsets)==len(new_offsets)==vertices+1 and old_offsets[0]==new_offsets[0]==0 and old_offsets[-1]==new_offsets[-1]==arcs
    assert len(new_targets)==len(old_costs)==len(new_costs)==len(old_reverse)==len(new_reverse)==arcs
    assert all(a<=b for a,b in zip(old_offsets,old_offsets[1:])) and all(a<=b for a,b in zip(new_offsets,new_offsets[1:]))
    assert all(value<vertices for value in old_targets) and all(value<vertices for value in new_targets)
    old_to_new=array('I',[0])*vertices;previous=(-1,-1)
    keys=unpack24(raw(output,'cell-keys.u24'));starts=unpack24(raw(output,'cell-offsets.u24'))
    assert len(starts)==len(keys)+1 and starts[0]==0 and starts[-1]==vertices
    assert all(a<b for a,b in zip(keys,keys[1:])) and all(a<b for a,b in zip(starts,starts[1:]))
    assert 6*len(keys)+3<=1048576
    cell=0
    for new,old in enumerate(order):
        assert old<vertices
        x,y=new_xy[2*new:2*new+2];assert old_xy[2*old:2*old+2]==array('i',[x,y]) and new_flags[new]==old_flags[old]
        key=morton(x,y);assert previous<(key,old);previous=(key,old);old_to_new[old]=new
        while new>=starts[cell+1]:cell+=1
        assert keys[cell]==key>>40
        assert new_offsets[new+1]-new_offsets[new]==old_offsets[old+1]-old_offsets[old]
    checked=0
    for new,old in enumerate(order):
        for position,arc in enumerate(range(old_offsets[old],old_offsets[old+1])):
            mapped=new_offsets[new]+position
            assert arc_map[arc]==mapped and new_targets[mapped]==old_to_new[old_targets[arc]]
            assert new_costs[mapped]==old_costs[arc] and new_reverse[mapped]==old_reverse[arc]
            checked+=1
    assert checked==arcs
    for prefix,value_name,arc_values in [('cost','cost-overflow-ticks.u32',False),('reverse','reverse-overflow-targets.u24',True)]:
        name=prefix+'-overflow-arcs.u24';old_keys=unpack24(raw(source,name));new_keys=unpack24(raw(output,name))
        old_values=unpack24(raw(source,value_name)) if arc_values else words(source,value_name,'I')
        new_values=unpack24(raw(output,value_name)) if arc_values else words(output,value_name,'I')
        assert len(old_keys)==len(old_values)==len(new_keys)==len(new_values)
        expected=sorted((arc_map[key],arc_map[value] if arc_values else value) for key,value in zip(old_keys,old_values))
        assert expected==list(zip(new_keys,new_values))
    old_pairs=unpack24(raw(source,'forbidden-turns.u24'));new_pairs=unpack24(raw(output,'forbidden-turns.u24'))
    assert len(old_pairs)%2==0 and len(old_pairs)==len(new_pairs)
    expected=array('Q',sorted((int(arc_map[a])<<24)|arc_map[b] for a,b in zip(old_pairs[::2],old_pairs[1::2])))
    actual=array('Q',((int(a)<<24)|b for a,b in zip(new_pairs[::2],new_pairs[1::2])))
    assert expected==actual
    return {'status':'independent_complete_lossless_spatial_permutation_audit_passed','verticesChecked':vertices,
            'directedArcsCostsPhysicalReversesChecked':checked,'forbiddenTurnPairsChecked':len(expected),
            'spatialCellsChecked':len(keys),'spatialIndexBytes':6*len(keys)+3,
            'secondsIndependentAudit':time.monotonic()-began,'sourcePbfReads':0,'sourceConstructorExecutions':0,
            'nativeLibraryExecutions':0,'snappingOrEtaOrAppQualified':False}
