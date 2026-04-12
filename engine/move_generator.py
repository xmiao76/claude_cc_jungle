"""Legal move generation for all pieces in Jungle."""

from __future__ import annotations

from config import (
    COLS, ROWS, TERRAIN, TERRAIN_RIVER, TERRAIN_DEN,
    DEN_BLACK, DEN_BLUE, RIVER_1, RIVER_2,
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
    """Precompute all valid river-jump endpoints for Lion and Tiger."""
    river_blocks = [RIVER_1, RIVER_2]
    for river in river_blocks:
        # Find all squares adjacent to this river block (not in river)
        for (c, r) in river:
            for (dc, dr) in _DIRS:
                nc, nr = c + dc, r + dr
                if not (0 <= nc < COLS and 0 <= nr < ROWS):
                    continue
                if (nc, nr) in river:
                    continue
                # (nc, nr) is a land square adjacent to the river.
                # Follow direction (dc, dr) from (nc, nr) across the river.
                lc, lr = nc - dc, nr - dr  # step back into river
                # Follow *back through* the river to find landing
                # Actually: from (nc,nr) in direction (-dc,-dr) we entered.
                # The jump direction is the SAME direction that got us here.
                # Jump starts at (nc, nr), goes in direction (dc, dr) but
                # wait — we want: piece at (nc, nr) jumps over river in
                # direction (dc, dr) is INTO the river... Let me recompute.
                # We want jumps FROM a land square, through the river, to a land square.
                # Scan: start at land square, move in direction, skip water squares.
                pass

    # Correct approach: for each land square adjacent to river, try all 4 directions
    all_river = RIVER_1 | RIVER_2
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
                # We have a river square adjacent in direction (dc,dr).
                # Follow the river to find the landing square.
                lc, lr = nc, nr
                while (0 <= lc < COLS and 0 <= lr < ROWS and
                       TERRAIN[lc][lr] == TERRAIN_RIVER):
                    lc += dc
                    lr += dr
                if not (0 <= lc < COLS and 0 <= lr < ROWS):
                    continue
                if TERRAIN[lc][lr] == TERRAIN_RIVER:
                    continue
                # Valid jump: (c,r) → (lc,lr) in direction (dc,dr)
                entry = _JUMP_TABLE.setdefault((c, r), [])
                # Store: direction + landing square
                entry.append((dc, dr, lc, lr))


_build_jump_table()


def _can_jump(animal: Animal, dc: int, dr: int) -> bool:
    """Return True if this animal can make a river jump in the given direction."""
    if animal == Animal.LION:
        return True   # Lion jumps both horizontally and vertically
    if animal == Animal.TIGER:
        return dr != 0  # Tiger jumps vertically only (dr != 0 means vertical)
    return False


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
