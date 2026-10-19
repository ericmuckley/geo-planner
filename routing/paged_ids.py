"""Original positive IDs in sparse bitmap pages; allocation ignores the highest ID."""

import sys


PAGE_IDS = 4096
PAGE_BYTES = PAGE_IDS // 8


class PagedIdSet:
    def __init__(self):
        self.pages, self.size = {}, 0

    def __len__(self): return self.size

    def add(self, identifier):
        if type(identifier) is not int or identifier <= 0: raise ValueError("Expected a positive integer OSM ID")
        key, offset = divmod(identifier, PAGE_IDS)
        page = self.pages.get(key)
        if page is None:
            page = self.pages[key] = bytearray(PAGE_BYTES)
        byte, mask = offset >> 3, 1 << (offset & 7)
        if not page[byte] & mask:
            page[byte] |= mask
            self.size += 1

    def __contains__(self, identifier):
        if type(identifier) is not int or identifier <= 0: return False
        key, offset = divmod(identifier, PAGE_IDS)
        page = self.pages.get(key)
        return page is not None and bool(page[offset >> 3] & (1 << (offset & 7)))

    def storage_summary(self):
        return {"kind": "sparse-original-id-bitmap", "ids": self.size, "idsPerPage": PAGE_IDS,
                "allocatedPages": len(self.pages), "bitmapBytes": len(self.pages) * PAGE_BYTES,
                "pythonContainerBytes": sys.getsizeof(self.pages) + sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in self.pages.items()),
                "scope": "Pages are keyed by original ID; no remapping or dense highest-ID allocation. Sparse IDs can waste a page each. Container bytes exclude allocator/runtime/source caches; measured cgroup peak governs admission."}
