"""Legal move generation, including Lion/Tiger river jumps.

Every move this module yields is fully legal (Jungle has no "check", so there
is nothing to filter afterwards). River jumps are served from a table built
once at import time; each entry carries its landing square and the river
squares crossed, so blocking (a Rat in the water) is a cheap scan.

River-jump ruleset (matching prompt.md's wording):
  * The "4 rows" jump  — along a *column*, crossing the 3 river rows
    (e.g. (1,2) -> (1,6)). LION ONLY.
  * The "3 cols" jump  — along a *row*, crossing the 2 river cols
    (e.g. (0,4) -> (3,4)). LION and TIGER.
  * A Rat on any crossed river square blocks the jump.

Internally an entry's ``four_row`` flag is ``dc == 0`` (column fixed, row
changes). The Tiger is allowed only when ``four_row`` is False.
"""

from __future__ import annotations

from config import (
    COLS,
    DEN_BLACK_SQ,
    DEN_BLUE_SQ,
    DIRS,
    IS_RIVER,
    NEIGHBORS,
    NUM_SQUARES,
    ROWS,
    TERRAIN,
    TERRAIN_RIVER,
)
from engine.board import Board, Move
from engine.pieces import Animal
from engine.rules import can_capture, is_jump_blocked

_RAT = int(Animal.RAT)
_TIGER = int(Animal.TIGER)
_LION = int(Animal.LION)
EMPTY = 0

# JUMP_TABLE[sq] -> tuple of (four_row: bool, landing_sq: int, river_path: tuple[int,...])
JUMP_TABLE: dict[int, tuple[tuple[bool, int, tuple[int, ...]], ...]] = {}
# Jump-readiness proxies for the evaluator. HAS_JUMP: any jump exists (Lion, which
# may make either crossing). HAS_JUMP_TIGER: a *3-col* (non-four_row) jump exists,
# i.e. one the Tiger is actually allowed to make.
HAS_JUMP: tuple[bool, ...] = ()
HAS_JUMP_TIGER: tuple[bool, ...] = ()


def _build_jump_table() -> None:
    global HAS_JUMP, HAS_JUMP_TIGER
    for c in range(COLS):
        for r in range(ROWS):
            if TERRAIN[c][r] == TERRAIN_RIVER:
                continue
            sq = c * ROWS + r
            for (dc, dr) in DIRS:
                nc, nr = c + dc, r + dr
                if not (0 <= nc < COLS and 0 <= nr < ROWS):
                    continue
                if TERRAIN[nc][nr] != TERRAIN_RIVER:
                    continue
                # Walk through consecutive river squares to the first non-river square.
                path = []
                lc, lr = nc, nr
                while 0 <= lc < COLS and 0 <= lr < ROWS and TERRAIN[lc][lr] == TERRAIN_RIVER:
                    path.append(lc * ROWS + lr)
                    lc += dc
                    lr += dr
                if not (0 <= lc < COLS and 0 <= lr < ROWS):
                    continue
                if TERRAIN[lc][lr] == TERRAIN_RIVER:
                    continue
                landing = lc * ROWS + lr
                four_row = dc == 0  # column fixed, row changes -> the "4 rows" jump
                entry = (four_row, landing, tuple(path))
                JUMP_TABLE[sq] = JUMP_TABLE.get(sq, ()) + (entry,)
    HAS_JUMP = tuple(sq in JUMP_TABLE for sq in range(NUM_SQUARES))
    HAS_JUMP_TIGER = tuple(
        any(not four_row for (four_row, _lsq, _p) in JUMP_TABLE.get(sq, ()))
        for sq in range(NUM_SQUARES)
    )


_build_jump_table()


def _own_den(color: int) -> int:
    return DEN_BLUE_SQ if color == 0 else DEN_BLACK_SQ


def generate_moves(board: Board, color: int) -> list[Move]:
    """All legal moves for ``color``."""
    moves: list[Move] = []
    sq = board.sq
    own_den = _own_den(color)
    append = moves.append

    for s, code in enumerate(sq):
        if code == EMPTY or (code >> 4) != color:
            continue
        animal = code & 0x0F

        # --- orthogonal steps ---
        for nsq in NEIGHBORS[s]:
            if nsq == own_den:
                continue                       # may never enter your own den
            if IS_RIVER[nsq] and animal != _RAT:
                continue                       # only the Rat may enter the river
            target = sq[nsq]
            if target == EMPTY:
                append(Move(s, nsq, 0))
            elif (target >> 4) != color and can_capture(
                color, animal, s, target >> 4, target & 0x0F, nsq
            ):
                append(Move(s, nsq, target))

        # --- river jumps (Lion and Tiger only) ---
        if animal == _LION or animal == _TIGER:
            for (four_row, landing, path) in JUMP_TABLE.get(s, ()):
                if animal == _TIGER and four_row:
                    continue                   # Tiger cannot make the "4 rows" jump
                if is_jump_blocked(path, board):
                    continue
                if landing == own_den:
                    continue
                target = sq[landing]
                if target == EMPTY:
                    append(Move(s, landing, 0, True))
                elif (target >> 4) != color and can_capture(
                    color, animal, s, target >> 4, target & 0x0F, landing
                ):
                    append(Move(s, landing, target, True))

    return moves


def generate_captures(board: Board, color: int) -> list[Move]:
    """Only capturing moves for ``color`` (used by the quiescence search)."""
    moves: list[Move] = []
    sq = board.sq
    append = moves.append

    for s, code in enumerate(sq):
        if code == EMPTY or (code >> 4) != color:
            continue
        animal = code & 0x0F

        for nsq in NEIGHBORS[s]:
            if IS_RIVER[nsq] and animal != _RAT:
                continue
            target = sq[nsq]
            if target != EMPTY and (target >> 4) != color and can_capture(
                color, animal, s, target >> 4, target & 0x0F, nsq
            ):
                append(Move(s, nsq, target))

        if animal == _LION or animal == _TIGER:
            for (four_row, landing, path) in JUMP_TABLE.get(s, ()):
                if animal == _TIGER and four_row:
                    continue
                target = sq[landing]
                if target == EMPTY or (target >> 4) == color:
                    continue
                if is_jump_blocked(path, board):
                    continue
                if can_capture(color, animal, s, target >> 4, target & 0x0F, landing):
                    append(Move(s, landing, target, True))

    return moves


def has_any_move(board: Board, color: int) -> bool:
    """Fast check: does ``color`` have at least one legal move?"""
    sq = board.sq
    own_den = _own_den(color)
    for s, code in enumerate(sq):
        if code == EMPTY or (code >> 4) != color:
            continue
        animal = code & 0x0F
        for nsq in NEIGHBORS[s]:
            if nsq == own_den:
                continue
            if IS_RIVER[nsq] and animal != _RAT:
                continue
            target = sq[nsq]
            if target == EMPTY:
                return True
            if (target >> 4) != color and can_capture(
                color, animal, s, target >> 4, target & 0x0F, nsq
            ):
                return True
        if animal == _LION or animal == _TIGER:
            for (four_row, landing, path) in JUMP_TABLE.get(s, ()):
                if animal == _TIGER and four_row:
                    continue
                if landing == own_den or is_jump_blocked(path, board):
                    continue
                target = sq[landing]
                if target == EMPTY:
                    return True
                if (target >> 4) != color and can_capture(
                    color, animal, s, target >> 4, target & 0x0F, landing
                ):
                    return True
    return False
