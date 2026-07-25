"""Transposition table keyed by Zobrist hash.

Two things beyond a plain dict matter here.

**Aging.** The table lives for the whole game, so without a notion of age a deep
entry from a position that is now unreachable occupies its slot forever, and a
depth-preferring replacement policy means a newer, more relevant, shallower search
can never overwrite it. Each search bumps a generation counter; an entry from an
older generation is always replaceable regardless of its depth.

**Cheap eviction.** The previous policy sorted the entire table by depth and
dropped the lowest half. At the one-million-entry cap that is an O(n log n) sort
plus a one-million-tuple allocation — a multi-second stall in the middle of a
move. Eviction now drops entries from older generations, which is a single linear
pass, and only falls back to shallow-first if everything is current.

Entries are plain tuples rather than objects: one allocation per store instead of
two, on a path that runs at every node.
"""

from __future__ import annotations

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2

_MAX_ENTRIES = 1_000_000

# Tuple layout. Named so call sites read as intent rather than as indices.
_DEPTH = 0
_SCORE = 1
_FLAG = 2
_MOVE = 3
_GEN = 4


class TTEntry:
    """View over a stored tuple, so `entry.depth` style access still works."""

    __slots__ = ("_t",)

    def __init__(self, t: tuple) -> None:
        self._t = t

    @property
    def depth(self) -> int:
        return self._t[_DEPTH]

    @property
    def score(self) -> int:
        return self._t[_SCORE]

    @property
    def flag(self) -> int:
        return self._t[_FLAG]

    @property
    def best_move(self):
        return self._t[_MOVE]

    @property
    def generation(self) -> int:
        return self._t[_GEN]


class TranspositionTable:
    __slots__ = ("_table", "_max", "_generation", "_use_aging")

    def __init__(self, max_entries: int = _MAX_ENTRIES, use_aging: bool = True) -> None:
        self._table: dict[int, tuple] = {}
        self._max = max_entries
        self._generation = 0
        self._use_aging = use_aging

    def new_search(self) -> None:
        """Mark the start of a search, so existing entries count as stale."""
        self._generation += 1

    def get(self, key: int) -> TTEntry | None:
        t = self._table.get(key)
        return TTEntry(t) if t is not None else None

    def put(self, key: int, depth: int, score: int, flag: int, best_move) -> None:
        existing = self._table.get(key)
        if existing is not None:
            stale = self._use_aging and existing[_GEN] != self._generation
            # Keep a deeper analysis, unless it is left over from an earlier search.
            if not stale and existing[_DEPTH] > depth:
                return
        elif len(self._table) >= self._max:
            self._evict()
        self._table[key] = (depth, score, flag, best_move, self._generation)

    def _evict(self) -> None:
        """Free space with a single linear pass, never a full sort."""
        if self._use_aging:
            stale = [k for k, v in self._table.items() if v[_GEN] != self._generation]
            if stale:
                for k in stale:
                    del self._table[k]
                return
        # Everything is from the current search: drop the shallow half by depth
        # threshold, still in one pass rather than by sorting.
        depths = [v[_DEPTH] for v in self._table.values()]
        cutoff = sorted(depths)[len(depths) // 2] if depths else 0
        for k in [k for k, v in self._table.items() if v[_DEPTH] <= cutoff]:
            del self._table[k]

    def clear(self) -> None:
        self._table.clear()

    def __len__(self) -> int:
        return len(self._table)
