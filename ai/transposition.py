"""A small transposition table for the search.

Entries are keyed by the position hash and store the search depth, a bound
flag, the score, and the best move found — the best move drives move ordering
even when the stored bound is not deep enough to cause a cutoff.
"""

from __future__ import annotations

from typing import NamedTuple

from engine.board import Move

EXACT = 0
LOWER = 1   # score is a lower bound (fail-high / beta cutoff)
UPPER = 2   # score is an upper bound (fail-low)

_MAX_ENTRIES = 1 << 20   # cap memory; oldest generation is evicted on overflow


class Entry(NamedTuple):
    depth: int
    flag: int
    score: int
    move: Move | None
    gen: int


class TranspositionTable:
    def __init__(self) -> None:
        self._table: dict[int, Entry] = {}
        self.generation = 0

    def clear(self) -> None:
        self._table.clear()
        self.generation = 0

    def probe(self, key: int) -> Entry | None:
        return self._table.get(key)

    def store(self, key: int, depth: int, flag: int, score: int, move: Move | None) -> None:
        prev = self._table.get(key)
        # Prefer deeper results from the current generation; always allow a
        # newer generation to overwrite a stale entry.
        if prev is not None and prev.gen == self.generation and prev.depth > depth:
            return
        if len(self._table) >= _MAX_ENTRIES and key not in self._table:
            self._evict()
        self._table[key] = Entry(depth, flag, score, move, self.generation)

    def _evict(self) -> None:
        """Drop entries older than the current generation; if none, clear."""
        gen = self.generation
        stale = [k for k, e in self._table.items() if e.gen != gen]
        if stale:
            for k in stale:
                del self._table[k]
        else:
            self._table.clear()
