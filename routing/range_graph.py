"""Run the frozen compact JSON loader on a read-only, range-advised UTF-8 stream."""

import codecs

from compact_load import load_graph as frozen_load_graph
from xml_stream import RangeReader


class GraphPath:
    def __init__(self, path, **options):
        self.path, self.options = path, options

    def open(self):
        return TextReader(self.path, **self.options)


class TextReader:
    def __init__(self, path, **options):
        self.reader = RangeReader(path, **options)
        self.decoder = codecs.getincrementaldecoder("utf-8")()

    def __enter__(self):
        self.reader.__enter__()
        return self

    def read(self, size=-1):
        while True:
            block = self.reader.read(size)
            text = self.decoder.decode(block, final=not block and size != 0)
            if text or not block: return text

    def __exit__(self, *error):
        return self.reader.__exit__(*error)


def load_graph(path, block_size=1 << 20, **options):
    return frozen_load_graph(GraphPath(path, **options), block_size)
