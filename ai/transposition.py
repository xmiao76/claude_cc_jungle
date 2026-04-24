"""Transposition table using Zobrist hashes.

Replacement strategy: depth-prefer. A new entry only overwrites an existing
entry of strictly greater depth; equal or shallower depths are replaced.
On overflow the lowest-depth half is evicted.
"""

from __future__ import annotations

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2

_MAX_ENTRIES = 1_000_000


class TTEntry:
    __slots__ = ("depth", "score", "flag", "best_move")

    def __init__(self, depth: int, score: int, flag: int, best_move) -> None:
        self.depth = depth
        self.score = score
        self.flag = flag
        self.best_move = best_move


class TranspositionTable:
    def __init__(self, max_entries: int = _MAX_ENTRIES) -> None:
        self._table: dict[int, TTEntry] = {}
        self._max = max_entries

    def get(self, key: int) -> TTEntry | None:
        return self._table.get(key)

    def put(self, key: int, depth: int, score: int, flag: int, best_move) -> None:
        existing = self._table.get(key)
        if existing is not None and existing.depth > depth:
            return  # keep deeper analysis
        if existing is None and len(self._table) >= self._max:
            self._evict_low_depth()
        self._table[key] = TTEntry(depth, score, flag, best_move)

    def _evict_low_depth(self) -> None:
        # Sort by depth ascending; drop the lowest half.
        items = sorted(self._table.items(), key=lambda kv: kv[1].depth)
        cut = self._max // 2
        for k, _ in items[:cut]:
            del self._table[k]

    def clear(self) -> None:
        self._table.clear()
