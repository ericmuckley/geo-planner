"""Capped offline experiments: checkpoint resources and sample cgroup composition."""

from pathlib import Path
import resource
import threading
import time

from compact_storage import save_json
from import_capacity import resources


STAT_FIELDS = ("anon", "file", "kernel", "file_mapped", "file_dirty", "file_writeback", "shmem", "slab", "pagetables", "sock")


def sample():
    result = resources()
    root = Path("/sys/fs/cgroup")
    for name in ("memory.stat", "memory.swap.events", "memory.swap.max", "memory.swap.current", "memory.swap.peak"):
        value = (root / name).read_text().strip()
        result[name] = dict((key, int(number)) for key, number in (line.split() for line in value.splitlines())) if name in {"memory.stat", "memory.swap.events"} else value
    result["maxChildRssKiB"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return result


def check_policy(value):
    if value["memory.max"] != str(4 * 1024 ** 3) or value["memory.swap.max"] != "0":
        raise ValueError("Require 4 GiB container RAM and swap disabled")
    if value["memory.swap.current"] != "0" or value["memory.swap.peak"] != "0": raise ValueError("Unexpected container swap")
    if any(int(value["memory.events"][key]) for key in ("oom", "oom_kill", "oom_group_kill")):
        raise ValueError("Container encountered an OOM event")


class Monitor:
    def __init__(self, output, interval=0.2):
        self.output, self.interval, self.started = output, interval, time.perf_counter()
        self.stop_event, self.lock = threading.Event(), threading.Lock()
        self.count, self.max_stats, self.highest = 0, {}, None
        self.checkpoints = {}
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def collect(self):
        value = sample()
        with self.lock:
            self.count += 1
            if self.highest is None or int(value["memory.current"]) > int(self.highest["memory.current"]): self.highest = value
            for key in STAT_FIELDS: self.max_stats[key] = max(self.max_stats.get(key, 0), value["memory.stat"].get(key, 0))
        return value

    def loop(self):
        while not self.stop_event.wait(self.interval): self.collect()

    def __enter__(self):
        check_policy(self.collect())
        self.thread.start()
        return self

    def checkpoint(self, stage):
        value = self.collect()
        check_policy(value)
        value["elapsedMs"] = (time.perf_counter() - self.started) * 1000
        self.checkpoints[stage] = value
        save_json(self.output / "progress.json", {"resourceCheckpoints": self.checkpoints, "sampling": self.summary()})
        print(f"{stage}: {value['elapsedMs'] / 1000:.2f} s; cgroup peak {value['memory.peak']}; anon {value['memory.stat'].get('anon')}; file {value['memory.stat'].get('file')}; swap max/peak 0/0", flush=True)

    def summary(self):
        with self.lock:
            return {"intervalSeconds": self.interval, "samples": self.count, "maxObservedStatBytes": dict(self.max_stats),
                    "highestCurrentSample": self.highest, "scope": "Periodic samples can miss brief composition peaks. Field maxima are not simultaneous and must not be summed. memory.peak is a separate cumulative kernel counter; host/VM paging is unmeasured."}

    def __exit__(self, *error):
        self.stop_event.set(); self.thread.join()
