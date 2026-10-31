"""Capacity-census resources include the preserved stopped full-index allocation."""
import time

from coarse_osm_country_screen_v1 import OwnedStorage,owned_usage,resource_metrics
from coarse_osm_country_screen_v4 import Resources
from coarse_timing_input import require

TMP=256*1024**2
FILE=64*1024**2
TOTAL=64*1024**3
ORIGINAL_RETAINED=38811541607
STOPPED_RUN_ALLOCATED=14512766976
RETAINED=ORIGINAL_RETAINED+STOPPED_RUN_ALLOCATED
OWNED=TOTAL-RETAINED-TMP


class CellResources(Resources):
    def check(self,*,force=False,projected=0):
        now=time.monotonic();require(now-self.began<self.seconds,'Cell census worker deadline')
        if not force and not projected and now-self.last_sample<1:return
        work,tmp=owned_usage(self.root),owned_usage(self.tmp)
        require(work['conservativeAllocatedBytes']+projected+1048576<=OWNED,'Cell census retained-working cap')
        require(tmp['allocatedBytes']<=TMP and work['entries']+tmp['entries']+1<=4096,'Cell census tmp/namespace cap')
        require(all(p.stat().st_size<=FILE for p in self.root.rglob('*') if p.is_file()),'Cell census file cap')
        self.latest={'work':work,'tmp':tmp,'cgroup':resource_metrics(),'seconds':now-self.began}
        for name in self.peaks:self.peaks[name]=max(self.peaks[name],work[name])
        self.last_sample=now;self.samples+=1;self.sampled()

    def result(self):
        self.check(force=True)
        return {'latest':self.latest,'observedWorkPeaks':self.peaks,'samples':self.samples,
                'retainedReservationBytes':RETAINED,'ownedLimitBytesExcludingTmp':OWNED,'totalRetainedWorkingBytesIncludingTmp':TOTAL,
                'scope':'Conservative owned allocation plus retained input reservation and fixed tmp allowance. Kernel cgroup peak covers the whole worker; no graph-search or pure Python-heap timing/memory claim.'}


class CellStorage(OwnedStorage):
    def __init__(self,root,resources):
        super().__init__(root,limit=OWNED,file_limit=FILE,entries=4096);self.resources=resources

    def write(self,path,raw):
        self.resources.check(force=True,projected=len(raw));super().write(path,raw);self.resources.check(force=True)
