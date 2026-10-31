"""Independent clipping/materialization over its own selected-state spool."""
import hashlib
from pathlib import Path

from coarse_osm_bulk_audit import crossing
from coarse_osm_records import canonical
from coarse_osm_selected_store_v1 import SelectedStore
from coarse_timing_input import require


class SelectedAudit(SelectedStore):
    def __init__(self,path,proposal,run,**options):
        super().__init__(path,proposal['windows'],run,**options);self.proposal=proposal

    def way_with_points(self,raw,points):
        low_x=min(p[0] for p in points);high_x=max(p[0] for p in points)
        low_y=min(p[1] for p in points);high_y=max(p[1] for p in points)
        for window in self.proposal['windows']:
            left,bottom,right,top=window['bbox']
            if high_x<left or low_x>right or high_y<bottom or low_y>top:continue
            if crossing(points,window['bbox']):
                self.add(window['id'],('way',raw['id']))
                for identity in raw['nodes']:self.add(window['id'],('node',identity))
        if self.contains(('way',raw['id'])):self.keep(raw)

    def relation(self,raw):
        linked={(m['type'],m['ref']) for m in raw['members'] if m['type'] in ('node','way')}
        windows=set()
        for key in linked:windows.update(self.member_windows(key))
        for name in self.windows:
            if name in windows:self.add(name,('relation',raw['id']))
        if self.contains(('relation',raw['id'])):self.keep(raw)

    def compare(self,path):
        self.complete();snapshot=self.run.state['publisherStateUtc'];count=total=0
        # Rebuild each expected record from the audit database, never primary hints.
        with Path(path).open('rb') as stream:
            for key,element in self.iter_objects():
                expected={'publisherStateUtc':snapshot,'element':element,'elementSha256':hashlib.sha256(canonical(element)).hexdigest(),
                          'windowIds':self.member_windows(key)}
                if key[0]=='way':
                    dependencies=[self.raw(('node',n)) for n in element['nodes']]
                    expected['geometryDependencySha256']=hashlib.sha256(canonical([snapshot,dependencies])).hexdigest()
                line=stream.readline(self.run.caps['singleNormalizedElementBytes']+1)
                require(line==canonical(expected)+b'\n','Selected independent output/geometry/membership mismatch')
                count+=1;total+=len(line)
            require(not stream.read(1),'Selected audit extra output')
        require(count==self.run.state['retainedElements'] and total==self.run.state['extractBytes'],'Selected audit output accounting')
        require(self.occurrences==self.run.state['windowOccurrences'],'Selected audit occurrence accounting')
