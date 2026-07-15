"""Legal move generation for all pieces in Jungle."""

from __future__ import annotations

from config import (
    COLS, ROWS, TERRAIN, TERRAIN_RIVER,
    DEN_BLACK, DEN_BLUE,
)
from engine.board import Board, Move
from engine.pieces import Animal, Color
from engine.rules import can_capture, is_jump_blocked

# Cardinal directions
_DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]

# Integer ranks for the hot loops (Animal is an IntEnum; comparing plain ints
# avoids constructing an enum per piece per node).
_RAT = int(Animal.RAT)
_TIGER = int(Animal.TIGER)
_LION = int(Animal.LION)

# Precomputed jump endpoints for Lion and Tiger.
# For each starting square on the edge of a river block, store a list of
# (dc, dr, landing_col, landing_row) where dc/dr is the jump direction.
# Built lazily at first import.
_JUMP_TABLE: dict[tuple[int, int], list[tuple[int, int, int, int]]] = {}


def _build_jump_table() -> None:
    """Precompute all valid river-jump endpoints for Lion and Tiger.

    For each land square adjacent to a river, follow each cardinal direction
    through the river to the first non-river square; that pair forms a jump.
    """
    for c in range(COLS):
        for r in range(ROWS):
            if TERRAIN[c][r] == TERRAIN_RIVER:
                continue
            for (dc, dr) in _DIRS:
                nc, nr = c + dc, r + dr
                if not (0 <= nc < COLS and 0 <= nr < ROWS):
                    continue
                if TERRAIN[nc][nr] != TERRAIN_RIVER:
                    continue
                lc, lr = nc, nr
                while (0 <= lc < COLS and 0 <= lr < ROWS and
                       TERRAIN[lc][lr] == TERRAIN_RIVER):
                    lc += dc
                    lr += dr
                if not (0 <= lc < COLS and 0 <= lr < ROWS):
                    continue
                if TERRAIN[lc][lr] == TERRAIN_RIVER:
                    continue
                _JUMP_TABLE.setdefault((c, r), []).append((dc, dr, lc, lr))


_build_jump_table()


def _can_jump(animal: Animal, dc: int, dr: int) -> bool:
    """Return True if this animal can leap a river crossing in direction (dc, dr).

    The river has two crossings:
      - "Horizontal" crossing = 2 river squares (column-axis leap, dc != 0).
      - "Vertical"   crossing = 3 river squares (row-axis    leap, dr != 0).

    Lion can leap up to 3 squares -> both crossings.
    Tiger can leap up to 2 squares -> the horizontal crossing only.
    """
    if animal == Animal.LION:
        return True
    if animal == Animal.TIGER:
        return dc != 0   # horizontal (2-square) jump only
    return False


def is_capture(move: Move) -> bool:
    return move.captured != 0


def generate_capture_moves(board: Board, color: Color) -> list[Move]:
    """Generate only capture moves — used by quiescence search."""
    return [m for m in generate_legal_moves(board, color) if m.captured != 0]


def generate_noisy_moves(board: Board, color: Color) -> list[Move]:
    """Captures plus den-entry (immediately winning) moves.

    Used by quiescence so a winning den dash sitting just past the horizon is
    not missed. A den-entry move is always a non-capture (the enemy den is
    empty), so it would otherwise be invisible to a capture-only quiescence.
    """
    opp_den = DEN_BLACK if color == Color.BLUE else DEN_BLUE
    return [m for m in generate_legal_moves(board, color)
            if m.captured != 0 or (m.tc, m.tr) == opp_den]


def generate_noisy_only(board: Board, color: Color) -> list[Move]:
    """Captures + den entries, generated directly (v1.4 speed pack).

    Behaviorally identical to :func:`generate_noisy_moves`, but never builds
    the (much larger) quiet-move list. Quiescence calls this at every node,
    where quiet moves are generated only to be thrown away by the filter.
    """
    moves: list[Move] = []
    append = moves.append
    get = board.get
    terrain = TERRAIN
    jump_table_get = _JUMP_TABLE.get
    cols = COLS
    rows = ROWS
    is_blue = color == Color.BLUE
    own_den = DEN_BLUE if is_blue else DEN_BLACK
    opp_den = DEN_BLACK if is_blue else DEN_BLUE

    for pid, (c, r) in board.pieces_of(color).items():
        rank = pid if pid > 0 else -pid

        # --- Normal steps ---
        for (dc, dr) in _DIRS:
            nc = c + dc
            nr = r + dr
            if not (0 <= nc < cols and 0 <= nr < rows):
                continue
            if (nc, nr) == own_den:
                continue
            if terrain[nc][nr] == TERRAIN_RIVER and rank != _RAT:
                continue
            target_pid = get(nc, nr)
            if target_pid == 0:
                if (nc, nr) == opp_den:
                    append(Move(c, r, nc, nr, 0))
            elif (target_pid > 0) != is_blue:
                if can_capture(pid, target_pid, c, r, nc, nr, board):
                    append(Move(c, r, nc, nr, target_pid))

        # --- River jumps (Lion and Tiger only) ---
        if rank == _LION or rank == _TIGER:
            for (dc, dr, lc, lr) in jump_table_get((c, r), ()):
                if rank == _TIGER and dc == 0:
                    continue   # Tiger: horizontal (2-square) jumps only
                if (lc, lr) == own_den:
                    continue
                if is_jump_blocked(c, r, lc, lr, board):
                    continue
                land_pid = get(lc, lr)
                if land_pid == 0:
                    if (lc, lr) == opp_den:
                        append(Move(c, r, lc, lr, 0))
                elif (land_pid > 0) != is_blue:
                    if can_capture(pid, land_pid, c, r, lc, lr, board):
                        append(Move(c, r, lc, lr, land_pid))

    return moves


def generate_legal_moves(board: Board, color: Color) -> list[Move]:
    """Generate all legal moves for *color* on *board*."""
    moves: list[Move] = []
    append = moves.append
    get = board.get
    terrain = TERRAIN
    jump_table_get = _JUMP_TABLE.get
    cols = COLS
    rows = ROWS
    is_blue = color == Color.BLUE
    own_den = DEN_BLUE if is_blue else DEN_BLACK

    for pid, (c, r) in board.pieces_of(color).items():
        rank = pid if pid > 0 else -pid

        # --- Normal steps (all pieces) ---
        for (dc, dr) in _DIRS:
            nc = c + dc
            nr = r + dr
            if not (0 <= nc < cols and 0 <= nr < rows):
                continue

            # Cannot enter own den
            if (nc, nr) == own_den:
                continue

            # Only Rat can enter river squares
            if terrain[nc][nr] == TERRAIN_RIVER and rank != _RAT:
                continue

            target_pid = get(nc, nr)

            if target_pid == 0:
                # Empty square
                append(Move(c, r, nc, nr, 0))
            elif (target_pid > 0) != is_blue:
                # Enemy piece — check capture legality
                if can_capture(pid, target_pid, c, r, nc, nr, board):
                    append(Move(c, r, nc, nr, target_pid))
            # else: own piece — skip

        # --- River jumps (Lion and Tiger only) ---
        if rank == _LION or rank == _TIGER:
            for (dc, dr, lc, lr) in jump_table_get((c, r), ()):
                if rank == _TIGER and dc == 0:
                    continue   # Tiger cannot make the vertical (3-square) jump
                # Cannot land on own den
                if (lc, lr) == own_den:
                    continue
                # Check for rat blocking the river
                if is_jump_blocked(c, r, lc, lr, board):
                    continue
                # Check landing square
                land_pid = get(lc, lr)
                if land_pid == 0:
                    append(Move(c, r, lc, lr, 0))
                elif (land_pid > 0) != is_blue:
                    if can_capture(pid, land_pid, c, r, lc, lr, board):
                        append(Move(c, r, lc, lr, land_pid))

    return moves
