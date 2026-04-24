"""Legal move generation for all pieces in Jungle."""

from __future__ import annotations

from config import (
    COLS, ROWS, TERRAIN, TERRAIN_RIVER,
    DEN_BLACK, DEN_BLUE,
)
from engine.board import Board, Move
from engine.pieces import Animal, Color, piece_id_color, piece_id_animal
from engine.rules import can_capture, is_jump_blocked

# Cardinal directions
_DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]

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


def generate_legal_moves(board: Board, color: Color) -> list[Move]:
    """Generate all legal moves for *color* on *board*."""
    moves: list[Move] = []
    own_den = DEN_BLUE if color == Color.BLUE else DEN_BLACK

    for pid, (c, r) in list(board.pieces_of(color).items()):
        animal = piece_id_animal(pid)

        # --- Normal steps (all pieces) ---
        for (dc, dr) in _DIRS:
            nc, nr = c + dc, r + dr
            if not (0 <= nc < COLS and 0 <= nr < ROWS):
                continue

            # Cannot enter own den
            if (nc, nr) == own_den:
                continue

            target_terrain = TERRAIN[nc][nr]

            # Only Rat can enter river squares
            if target_terrain == TERRAIN_RIVER and animal != Animal.RAT:
                continue

            target_pid = board.get(nc, nr)

            if target_pid == 0:
                # Empty square
                moves.append(Move(c, r, nc, nr, 0))
            elif piece_id_color(target_pid) != color:
                # Enemy piece — check capture legality
                if can_capture(pid, target_pid, c, r, nc, nr, board):
                    moves.append(Move(c, r, nc, nr, target_pid))
            # else: own piece — skip

        # --- River jumps (Lion and Tiger only) ---
        if animal in (Animal.LION, Animal.TIGER):
            jump_list = _JUMP_TABLE.get((c, r), [])
            for (dc, dr, lc, lr) in jump_list:
                if not _can_jump(animal, dc, dr):
                    continue
                # Cannot land on own den
                if (lc, lr) == own_den:
                    continue
                # Check for rat blocking the river
                if is_jump_blocked(c, r, lc, lr, board):
                    continue
                # Check landing square
                land_pid = board.get(lc, lr)
                if land_pid == 0:
                    moves.append(Move(c, r, lc, lr, 0))
                elif piece_id_color(land_pid) != color:
                    if can_capture(pid, land_pid, c, r, lc, lr, board):
                        moves.append(Move(c, r, lc, lr, land_pid))

    return moves
