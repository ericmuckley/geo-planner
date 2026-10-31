"""Explicit network-free Linux resource probe; never runs on import."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from coarse_osm_input import absolute_timeout
from coarse_timing_input import cgroup_limit, require
from run_timing_cache import network_guard


def probe():
    memory, network = cgroup_limit(), network_guard()
    require(memory == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}, 'Probe requires isolated1GiB/zero-swap container')
    tmp = os.statvfs('/tmp'); tmp_bytes = tmp.f_frsize * tmp.f_blocks
    require(0 < tmp_bytes <= 67108864, 'Probe requires bounded64MiB tmpfs')
    def events(): return dict(line.split() for line in Path('/sys/fs/cgroup/memory.events').read_text().splitlines())
    before = events()
    child = subprocess.run([sys.executable, '-B', '-c', 'value=bytearray(2*1024**3)'], capture_output=True, timeout=30)
    after = events()
    require(child.returncode == -signal.SIGKILL and int(after['oom_kill']) > int(before['oom_kill']), 'Cgroup did not kill over-limit child')
    watchdog = subprocess.run([sys.executable, '-B', '-c',
        'from coarse_timing_input import start_watchdog; import time; start_watchdog(.05); time.sleep(5)'], capture_output=True, timeout=5)
    require(watchdog.returncode == -signal.SIGKILL, 'Independent watchdog did not kill stalled child')
    began = time.monotonic(); expired = False
    try:
        with absolute_timeout(.03): time.sleep(5)
    except RuntimeError: expired = True
    require(expired and time.monotonic() - began < 3, 'POSIX absolute deadline failed')
    return {'memoryGuard': memory, 'networkGuard': network, 'tmpCapacityBytes': tmp_bytes,
        'overLimitChildKilledByCgroup': True, 'independentWatchdogKilledStalledChild': True,
        'absoluteDeadlineInterruptedBlockingCall': True, 'scope': 'Synthetic Linux control proof only; no live HTTP, capture latency or model memory/peak-memory qualification.'}


if __name__ == '__main__':
    print(json.dumps(probe(), indent=2))
