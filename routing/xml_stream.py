"""Read-only XML streams with cache advice for completed byte ranges."""

from contextlib import contextmanager
import os
from pathlib import Path
import xml.etree.ElementTree as ET

from lifetime_io import WINDOW
from paged_io import THRESHOLD


REQUESTS = []


def discard_range(descriptor, offset, length):
    os.posix_fadvise(descriptor, offset, length, os.POSIX_FADV_DONTNEED)


class RangeReader:
    def __init__(self, path, advise=True, window=WINDOW, threshold=THRESHOLD):
        if type(window) is not int or window <= 0 or type(threshold) is not int or threshold < 0:
            raise ValueError("Invalid read-advice bounds")
        self.path, self.advise, self.window, self.threshold = Path(path), advise, window, threshold
        self.stream = None
        self.consumed = self.completed = self.ranges = self.successful = self.errors = 0
        self.reads = self.largest_read = self.largest_range = 0
        self.eof = False
        self.last_error = None

    def __enter__(self):
        if self.stream is not None: raise ValueError("Reader contexts are single-use")
        self.stream = self.path.open("rb")
        self.size = os.fstat(self.stream.fileno()).st_size
        self.enabled = self.advise and self.size >= self.threshold
        return self

    def release(self, final=False):
        if not self.enabled: return
        while self.consumed - self.completed >= self.window or (final and self.consumed > self.completed):
            length = min(self.window, self.consumed - self.completed)
            try:
                discard_range(self.stream.fileno(), self.completed, length)
            except (OSError, AttributeError) as error:
                # Cache advice must not replace an XML/read exception during cleanup.
                self.errors += 1
                self.last_error = {"type": type(error).__name__, "message": str(error)}
            else:
                self.successful += length
            self.completed += length
            self.ranges += 1
            self.largest_range = max(self.largest_range, length)

    def read(self, size=-1):
        if self.stream is None or self.stream.closed: raise ValueError("read of closed file")
        block = self.stream.read(size)
        self.reads += 1
        self.consumed += len(block)
        self.largest_read = max(self.largest_read, len(block))
        if not block and size != 0: self.eof = True
        self.release(final=self.eof)
        return block

    def close(self):
        if self.stream is None or self.stream.closed: return
        try:
            self.release(final=True)
        finally:
            self.stream.close()
            REQUESTS.append({"path": str(self.path), "fileBytes": self.size, "readBytes": self.consumed,
                             "reads": self.reads, "maxReadBytes": self.largest_read, "enabled": self.enabled,
                             "windowBytes": self.window, "ranges": self.ranges, "attemptedBytes": self.completed,
                             "successfulAdviceBytes": self.successful, "maxRangeBytes": self.largest_range,
                             "adviceErrors": self.errors, "lastAdviceError": self.last_error,
                             "eofObserved": self.eof, "closed": self.stream.closed})

    def __exit__(self, *error):
        self.close()


@contextmanager
def parse_xml(path, events):
    # Own the handle explicitly, including consumer errors and early termination.
    with RangeReader(path) as stream:
        yield ET.iterparse(stream, events=events)


def report():
    return {"requests": list(REQUESTS), "windowBytes": WINDOW, "readThresholdBytes": THRESHOLD,
            "scope": "Read-only binary streams with unchanged read(size) results and XML events. Advice only for completed ranges <= 16 MiB on files >= 8 MiB, including partial completed ranges on close. No input sync/write, seek or global cache drop. Advice failure is recorded without masking parse/read exceptions; the parity worker requires successful advice on real enabled streams. Kernel eviction is advisory."}
