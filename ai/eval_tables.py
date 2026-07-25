"""Precomputed lookup tables for evaluation, built once at import.

Two kinds of table live here:

**Adjacency.** ``ADJACENT[(c, r)]`` is the list of in-bounds orthogonal
neighbours. Evaluation walks neighbours constantly, and doing the four bounds
checks inline at every step is a measurable cost when evaluation is ~two thirds
of search time.

**True distance to den.** ``DEN_DISTANCE[cls][den][(c, r)]`` is the minimum
number of *moves* for a piece of movement class ``cls`` to reach ``den`` from
``(c, r)`` on an empty board.

That last table replaces the Manhattan distance the evaluator used to use, which
is simply wrong on this board: it walks straight through the river as if the
water were not there. A Wolf on (1,2) is Manhattan-3 from the Blue den at (3,8)
by a path it can never take, while its real distance is far greater. Because den
proximity is one of the heaviest positional terms, that error mis-prices the
central race — the thing Jungle games are actually decided by.

Distances are computed by breadth-first search on an empty board, so they ignore
occupancy. That is the right approximation for a static evaluation: it measures
the geometry of the board, not the current traffic.
"""

from __future__ import annotations

from collections import deque

from config import COLS, DEN_BLACK, DEN_BLUE, ROWS, TERRAIN, TERRAIN_RIVER
from engine.pieces import Animal

# Movement classes. Pieces differ in which squares they can traverse, so they
# differ in how far they really are from a den.
CLS_WALKER = 0      # land only: Cat, Dog, Wolf, Leopard, Elephant
CLS_SWIMMER = 1     # may enter the river: Rat
CLS_LION = 2        # land, plus leaps over either river crossing
CLS_TIGER = 3       # land, plus the horizontal (2-square) leap only

_DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))

# Animal -> movement class.
MOVEMENT_CLASS: dict[int, int] = {
    int(Animal.RAT): CLS_SWIMMER,
    int(Animal.CAT): CLS_WALKER,
    int(Animal.DOG): CLS_WALKER,
    int(Animal.WOLF): CLS_WALKER,
    int(Animal.LEOPARD): CLS_WALKER,
    int(Animal.TIGER): CLS_TIGER,
    int(Animal.LION): CLS_LION,
    int(Animal.ELEPHANT): CLS_WALKER,
}


def _build_adjacency() -> dict[tuple[int, int], tuple[tuple[int, int], ...]]:
    table: dict[tuple[int, int], tuple[tuple[int, int], ...]] = {}
    for c in range(COLS):
        for r in range(ROWS):
            table[(c, r)] = tuple(
                (c + dc, r + dr)
                for dc, dr in _DIRS
                if 0 <= c + dc < COLS and 0 <= r + dr < ROWS
            )
    return table


ADJACENT = _build_adjacency()


def _jump_targets(c: int, r: int, cls: int) -> list[tuple[int, int]]:
    """Leap destinations for a jumper standing on (c, r), ignoring blockers.

    Mirrors ``engine.move_generator._build_jump_table``: walk from a land square
    through a contiguous run of river to the first non-river square.
    """
    if cls not in (CLS_LION, CLS_TIGER):
        return []
    out: list[tuple[int, int]] = []
    for dc, dr in _DIRS:
        nc, nr = c + dc, r + dr
        if not (0 <= nc < COLS and 0 <= nr < ROWS):
            continue
        if TERRAIN[nc][nr] != TERRAIN_RIVER:
            continue
        # A Tiger can only clear the 2-square (horizontal) crossing.
        if cls == CLS_TIGER and dc == 0:
            continue
        lc, lr = nc, nr
        while 0 <= lc < COLS and 0 <= lr < ROWS and TERRAIN[lc][lr] == TERRAIN_RIVER:
            lc += dc
            lr += dr
        if 0 <= lc < COLS and 0 <= lr < ROWS and TERRAIN[lc][lr] != TERRAIN_RIVER:
            out.append((lc, lr))
    return out


def _build_den_distance(cls: int, den: tuple[int, int]) -> dict[tuple[int, int], int]:
    """BFS the *whole* board outward from *den* for one movement class.

    Searching backwards from the den gives every square's distance in one pass.
    The step relation is symmetric here — a normal step and a river leap are both
    reversible — so a backward BFS yields the same distances as a forward one.
    """
    can_swim = cls == CLS_SWIMMER
    dist: dict[tuple[int, int], int] = {den: 0}
    queue: deque[tuple[int, int]] = deque([den])

    while queue:
        c, r = queue.popleft()
        d = dist[(c, r)] + 1

        neighbours = list(ADJACENT[(c, r)])
        neighbours.extend(_jump_targets(c, r, cls))

        for (nc, nr) in neighbours:
            if (nc, nr) in dist:
                continue
            # Only the Rat may stand in the river.
            if TERRAIN[nc][nr] == TERRAIN_RIVER and not can_swim:
                continue
            dist[(nc, nr)] = d
            queue.append((nc, nr))

    return dist


def _build_all_den_distances() -> dict[int, dict[tuple[int, int], dict[tuple[int, int], int]]]:
    return {
        cls: {den: _build_den_distance(cls, den) for den in (DEN_BLUE, DEN_BLACK)}
        for cls in (CLS_WALKER, CLS_SWIMMER, CLS_LION, CLS_TIGER)
    }


DEN_DISTANCE = _build_all_den_distances()

# Squares a piece can never reach are absent from the BFS map; treat them as
# effectively infinitely far without letting the value dominate arithmetic.
UNREACHABLE = 99


def den_distance(animal_rank: int, den: tuple[int, int], c: int, r: int) -> int:
    """Minimum moves for a piece of rank *animal_rank* to reach *den* from (c, r)."""
    cls = MOVEMENT_CLASS[animal_rank]
    return DEN_DISTANCE[cls][den].get((c, r), UNREACHABLE)
