"""Filtered capture resources reserve all prior data and both census banks."""
import hashlib
from pathlib import Path
import re
import time

from coarse_osm_country_screen_v1 import OwnedStorage,MAX_VISITS,owned_usage,resource_metrics
from coarse_osm_country_screen_v4 import Resources
from coarse_osm_cell_resources_v2 import RETAINED as PRIOR_RETAINED
from coarse_osm_country_screen_v6 import NativeScreen
from coarse_osm_records import canonical
from coarse_timing_input import require

GIB=1024**3
TMP=256*1024**2
RETAINED_WORK_LIMIT=64*GIB
# Reserve both census banks at their full logical ceilings plus metadata.
CENSUS_RESERVATION=4*GIB+64*1024**2
RETAINED=PRIOR_RETAINED+CENSUS_RESERVATION
OWNED_LIMIT=RETAINED_WORK_LIMIT-RETAINED-TMP
FILE_LIMIT=128*1024**2


class FullScreen(NativeScreen):
    def scan(self,path,snapshot,caps,**options):
        # The extractor's aggregate allowance covers two source passes. The C
        # ABI independently limits each invocation to one source's object count.
        per_pass=dict(caps)
        per_pass['scanObjectVisitsTotal']=min(per_pass['scanObjectVisitsTotal'],MAX_VISITS)
        return super().scan(path,snapshot,per_pass,**options)


class FullResources(Resources):
    def result(self):
        self.check(force=True)
        return {'latest':self.latest,'observedWorkPeaks':self.peaks,'samples':self.samples,
                'retainedReservationBytes':RETAINED,'retainedWorkingLimitBytes':RETAINED_WORK_LIMIT,
                'ownedWorkLimitBytesExcludingTmp':OWNED_LIMIT,
                'scope':'Conservative allocated owned bytes plus fixed retained reservation and tmp allowance; sampled around index writes and periodically elsewhere. Kernel memory peak includes page cache.'}

    def check(self,*,force=False,projected=0):
        now=time.monotonic();require(now-self.began<self.seconds,'Full worker deadline')
        if not force and not projected and now-self.last_sample<1:return
        work,tmp=owned_usage(self.root),owned_usage(self.tmp)
        require(work['conservativeAllocatedBytes']+projected+12288<=OWNED_LIMIT,'Full retained-working allocation cap')
        require(tmp['allocatedBytes']<=TMP and work['entries']+tmp['entries']+1<=4096,'Full tmp/namespace cap')
        require(all(path.stat().st_size<=FILE_LIMIT for path in self.root.rglob('*') if path.is_file()),'Full individual file cap')
        self.latest={'work':work,'tmp':tmp,'cgroup':resource_metrics(),'seconds':now-self.began}
        for name in self.peaks:self.peaks[name]=max(self.peaks[name],work[name])
        self.last_sample=now;self.samples+=1;self.sampled()


class CaptureStorage(OwnedStorage):
    def __init__(self,root,resources):
        super().__init__(root,limit=OWNED_LIMIT,file_limit=64*1024**2,entries=4096)
        self.resources=resources

    def write(self,path,raw):
        path=Path(path);relative=path.resolve().relative_to(self.root)
        require(len(relative.parts)==2 and relative.parts[0] in ('all-highway-primary-selection-cells','all-highway-independent-materialization-cells'),'Capture compact-bank namespace only')
        require(path.name in ('index.json','directory.bin') or (path.suffix=='.bin' and path.stem.isdigit()),'Capture bank filename')
        self.resources.check(force=True,projected=len(raw));super().write(path,raw);self.resources.check(force=True)

    def remove(self,path,size):
        require(False,'Capture preserves all output parts')
