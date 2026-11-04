"""Optional Bloom filter used only to skip database reads for keys that are definitely new.

Contract: `might_contain() == False` means the key was never added to THIS filter instance.
`True` only means "maybe" and must be verified against the database. The filter is never the
source of truth and never decides that something was crawled or indexed.
"""

import hashlib
import math
from collections.abc import Iterable, Iterator


class BloomFilter:
    def __init__(self, capacity: int, error_rate: float) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if not 0.0 < error_rate < 1.0:
            raise ValueError("error_rate must be between 0 and 1 (exclusive)")
        self.capacity = capacity
        self.error_rate = error_rate
        self.num_bits = max(8, math.ceil(-capacity * math.log(error_rate) / (math.log(2) ** 2)))
        self.num_hashes = max(1, round(self.num_bits / capacity * math.log(2)))
        self._bits = bytearray((self.num_bits + 7) // 8)
        self._count = 0

    def _positions(self, key: str) -> Iterator[int]:
        digest = hashlib.blake2b(key.encode("utf-8"), digest_size=16).digest()
        first = int.from_bytes(digest[:8], "little")
        second = int.from_bytes(digest[8:], "little") | 1
        for i in range(self.num_hashes):
            yield (first + i * second) % self.num_bits

    def add(self, key: str) -> None:
        already = True
        for pos in self._positions(key):
            byte, bit = divmod(pos, 8)
            if not self._bits[byte] >> bit & 1:
                already = False
                self._bits[byte] |= 1 << bit
        if not already:
            self._count += 1

    def might_contain(self, key: str) -> bool:
        return all(self._bits[pos // 8] >> (pos % 8) & 1 for pos in self._positions(key))

    __contains__ = might_contain

    @property
    def count(self) -> int:
        """Insertions that changed the filter (a lower bound on distinct keys added)."""
        return self._count

    @property
    def saturated(self) -> bool:
        return self._count >= self.capacity

    def estimated_false_positive_rate(self) -> float:
        return (1.0 - math.exp(-self.num_hashes * self._count / self.num_bits)) ** self.num_hashes


class SeenUrlFilter:
    """Wraps an optional BloomFilter. Without a filter, or once it is saturated, nothing is
    ever reported as absent, so callers always fall back to the authoritative store."""

    def __init__(self, capacity: int = 0, error_rate: float = 0.01, enabled: bool = False) -> None:
        self._capacity = capacity
        self._error_rate = error_rate
        self._bloom = BloomFilter(capacity, error_rate) if enabled else None

    @property
    def enabled(self) -> bool:
        return self._bloom is not None

    def rebuild(self, urls: Iterable[str]) -> None:
        if self._bloom is None:
            return
        fresh = BloomFilter(self._capacity, self._error_rate)
        for url in urls:
            fresh.add(url)
        self._bloom = fresh

    def add(self, url: str) -> None:
        if self._bloom is not None:
            self._bloom.add(url)

    def definitely_absent(self, url: str) -> bool:
        return (
            self._bloom is not None
            and not self._bloom.saturated
            and not self._bloom.might_contain(url)
        )
