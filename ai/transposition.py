"""Transposition table using Zobrist hashes."""

from __future__ import annotations

# Flag constants for transposition table entries
TT_EXACT = 0    # exact score
TT_LOWER = 1    # lower bound (alpha cutoff)
TT_UPPER = 2    # upper bound (beta cutoff)

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
        if len(self._table) >= self._max:
            # Simple eviction: clear half the table (remove oldest entries)
            keys = list(self._table.keys())
            for k in keys[: self._max // 2]:
                del self._table[k]
        self._table[key] = TTEntry(depth, score, flag, best_move)

    def clear(self) -> None:
        self._table.clear()
