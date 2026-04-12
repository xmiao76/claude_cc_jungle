"""Board evaluation function for Jungle AI."""

from __future__ import annotations

from config import DEN_BLACK, DEN_BLUE, TRAPS_BLACK, TRAPS_BLUE, TERRAIN, TERRAIN_RIVER
from engine.pieces import Animal, Color, piece_id_color, piece_id_animal, piece_id_rank
from engine.move_generator import generate_legal_moves

# ---------------------------------------------------------------------------
# Material values
# ---------------------------------------------------------------------------

PIECE_VALUE: dict[Animal, int] = {
    Animal.RAT: 100,
    Animal.CAT: 200,
    Animal.DOG: 300,
    Animal.WOLF: 400,
    Animal.LEOPARD: 500,
    Animal.TIGER: 600,
    Animal.LION: 700,
    Animal.ELEPHANT: 800,
}

# ---------------------------------------------------------------------------
# Den positions indexed by Color
# ---------------------------------------------------------------------------

_OPPONENT_DEN = {
    Color.BLUE: DEN_BLACK,   # Blue's goal is Black's den
    Color.BLACK: DEN_BLUE,
}

_OWN_DEN = {
    Color.BLUE: DEN_BLUE,
    Color.BLACK: DEN_BLACK,
}

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

_INF = 10_000_000


def evaluate(state, color: Color) -> int:
    """Evaluate board from *color*'s perspective. Higher = better for color."""
    board = state.board
    opponent = Color.BLACK if color == Color.BLUE else Color.BLUE

    # Terminal check
    winner = state.get_winner()
    if winner is not None:
        return _INF if winner == color else -_INF

    score = 0

    opp_den_c, opp_den_r = _OPPONENT_DEN[color]
    own_den_c, own_den_r = _OWN_DEN[color]

    my_pieces = board.pieces_of(color)
    opp_pieces = board.pieces_of(opponent)

    # 1. Material + positional scores
    for pid, (c, r) in my_pieces.items():
        animal = piece_id_animal(pid)
        score += PIECE_VALUE[animal]

        # Advancement toward opponent den (row-based)
        if color == Color.BLUE:
            adv = (8 - r)  # rows 0-8; closer to row 0 = more advanced
        else:
            adv = r         # closer to row 8 = more advanced

        score += adv * 10

        # Den proximity bonus
        dist = abs(c - opp_den_c) + abs(r - opp_den_r)
        if dist <= 3:
            score += (4 - dist) * 30

        # Rat strategic bonus: in water (blocks opponent jumps), near enemy elephant
        if animal == Animal.RAT:
            if TERRAIN[c][r] == TERRAIN_RIVER:
                score += 40
            # Check if adjacent to opponent Elephant
            ele_pid = -Animal.ELEPHANT if color == Color.BLUE else Animal.ELEPHANT
            for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nc, nr = c + dc, r + dr
                if 0 <= nc < 7 and 0 <= nr < 9:
                    if board.get(nc, nr) == ele_pid:
                        score += 60

    for pid, (c, r) in opp_pieces.items():
        animal = piece_id_animal(pid)
        score -= PIECE_VALUE[animal]

        if color == Color.BLACK:
            adv = (8 - r)
        else:
            adv = r
        score -= adv * 10

        dist = abs(c - own_den_c) + abs(r - own_den_r)
        if dist <= 3:
            score -= (4 - dist) * 30

    # 2. Trap control: opponent piece in our traps = rank 0 (big advantage)
    our_traps = TRAPS_BLUE if color == Color.BLUE else TRAPS_BLACK
    for pid, (c, r) in opp_pieces.items():
        if (c, r) in our_traps:
            score += 80

    # 3. Mobility bonus
    # (Skip for leaf eval to save time; only compute at depth 0)
    # Omitting here — adds ~30% overhead; not needed for good play at depth 4+

    return score
