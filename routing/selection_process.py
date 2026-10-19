"""Run the frozen paged selector in a child whose heap ends before completion."""

import argparse
import json
import os
from pathlib import Path
import time

from buffer_resources import Monitor
from compact_storage import save_json
from paged_select import select_ids


def run(args):
    progress = Path(args.progress)
    progress.mkdir()
    started = time.perf_counter()
    with Monitor(progress) as monitor:
        selection = select_ids(Path(args.source), json.loads(args.bounds), Path(args.ids), monitor.checkpoint)
        monitor.checkpoint("selected")
        save_json(Path(args.stats), {"pid": os.getpid(), "selection": selection, "resourceCheckpoints": monitor.checkpoints,
                  "sampling": monitor.summary(), "workerWallMs": (time.perf_counter() - started) * 1000})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "bounds", "ids", "stats", "progress"): parser.add_argument(f"--{name}", required=True)
    run(parser.parse_args())
