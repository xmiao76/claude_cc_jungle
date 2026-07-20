"""Full game state: initial layout, turn tracking, make/undo, win/draw rules.

``GameState`` wraps a :class:`~engine.board.Board` with everything the board
deliberately omits — whose turn it is, the move history (for undo), the
no-capture clock, repetition counts, and the game result.

Result values:
    None          -> game in progress
    Color.BLUE    -> Blue has won
    Color.BLACK   -> Black has won
    DRAW          -> drawn (threefold repetition or the no-capture limit)
"""

from __future__ import annotations

from config import DEN_BLACK_SQ, DEN_BLUE_SQ, ROWS
from engine.board import ZOBRIST_SIDE, Board, Move
from engine.move_generator import generate_moves, has_any_move
from engine.pieces import Animal, Color, code_color

DRAW = "draw"
DRAW_HALFMOVE_LIMIT = 100   # plies with no capture -> draw (50 moves per side)
REPETITION_LIMIT = 3        # a position seen this many times -> draw


def _initial_setup() -> list[tuple[int, int, int, int]]:
    """Standard Dou Shou Qi layout as ``(col, row, color, animal)`` tuples.

    Black occupies the top (rows 0-2); Blue is the 180-degree rotation of
    Black, so the start position is point-symmetric and fair.
    """
    black = [
        (0, 0, Animal.LION), (6, 0, Animal.TIGER),
        (1, 1, Animal.DOG), (5, 1, Animal.CAT),
        (0, 2, Animal.RAT), (2, 2, Animal.LEOPARD),
        (4, 2, Animal.WOLF), (6, 2, Animal.ELEPHANT),
    ]
    setup: list[tuple[int, int, int, int]] = []
    for (c, r, animal) in black:
        setup.append((c, r, int(Color.BLACK), int(animal)))
        setup.append((6 - c, 8 - r, int(Color.BLUE), int(animal)))
    return setup


INITIAL_SETUP = _initial_setup()

# Each color's target den (entering it wins).
ENEMY_DEN = {int(Color.BLUE): DEN_BLACK_SQ, int(Color.BLACK): DEN_BLUE_SQ}


class GameState:
    def __init__(self) -> None:
        self.board = Board()
        self.to_move: int = int(Color.BLUE)
        self.result: object | None = None
        self.halfmove_clock: int = 0
        self.hash: int = 0
        self.counts = [0, 0]                     # [blue, black] piece counts
        self._history: list[tuple[Move, int]] = []
        self._rep: dict[int, int] = {}
        self.new_game()

    # -- setup --------------------------------------------------------------

    def new_game(self) -> None:
        self.board.clear()
        for (c, r, color, animal) in INITIAL_SETUP:
            self.board.set_piece(c * ROWS + r, color, animal)
        self.to_move = int(Color.BLUE)
        self.result = None
        self.halfmove_clock = 0
        self.counts = [self.board.count(0), self.board.count(1)]
        self._history.clear()
        self.hash = self._position_key()
        self._rep = {self.hash: 1}

    def setup_position(self, pieces: dict[tuple[int, int], tuple[int, int]],
                       to_move: int = int(Color.BLUE)) -> None:
        """Test helper: place an arbitrary position. ``pieces`` maps
        ``(col, row) -> (color, animal)``."""
        self.board.clear()
        for (c, r), (color, animal) in pieces.items():
            self.board.set_piece(c * ROWS + r, int(color), int(animal))
        self.to_move = int(to_move)
        self.result = None
        self.halfmove_clock = 0
        self.counts = [self.board.count(0), self.board.count(1)]
        self._history.clear()
        self.hash = self._position_key()
        self._rep = {self.hash: 1}

    # -- hashing ------------------------------------------------------------

    def _position_key(self) -> int:
        key = self.board.zobrist
        if self.to_move == int(Color.BLACK):
            key ^= ZOBRIST_SIDE
        return key

    # -- moves --------------------------------------------------------------

    def legal_moves(self) -> list[Move]:
        if self.result is not None:
            return []
        return generate_moves(self.board, self.to_move)

    def make_move(self, move: Move, detect_no_moves: bool = True) -> None:
        mover = self.to_move
        self._history.append((move, self.halfmove_clock))

        self.board.apply(move)
        if move.captured != 0:
            self.counts[code_color(move.captured)] -= 1
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        self.to_move = mover ^ 1
        self.hash = self._position_key()
        self._rep[self.hash] = self._rep.get(self.hash, 0) + 1

        self.result = self._compute_result(move, mover, detect_no_moves)

    def undo_move(self) -> None:
        move, prev_halfmove = self._history.pop()
        # Drop the current position from the repetition table.
        n = self._rep.get(self.hash, 0)
        if n <= 1:
            self._rep.pop(self.hash, None)
        else:
            self._rep[self.hash] = n - 1

        self.to_move ^= 1
        self.board.revert(move)
        if move.captured != 0:
            self.counts[code_color(move.captured)] += 1
        self.halfmove_clock = prev_halfmove
        self.hash = self._position_key()
        self.result = None

    # -- result -------------------------------------------------------------

    def _compute_result(self, move: Move, mover: int, detect_no_moves: bool):
        # 1. Den entry: the mover reached the enemy den.
        if move.to == ENEMY_DEN[mover]:
            return Color(mover)
        # 2. Elimination: the opponent has no pieces left.
        if self.counts[self.to_move] == 0:
            return Color(mover)
        # 3. Draw: threefold repetition or the no-capture limit.
        if self._rep.get(self.hash, 0) >= REPETITION_LIMIT:
            return DRAW
        if self.halfmove_clock >= DRAW_HALFMOVE_LIMIT:
            return DRAW
        # 4. Stalemate == loss: the side to move has no legal reply.
        if detect_no_moves and not has_any_move(self.board, self.to_move):
            return Color(mover)
        return None

    @property
    def game_over(self) -> bool:
        return self.result is not None

    def winner(self) -> Color | None:
        return self.result if isinstance(self.result, Color) else None

    def is_draw(self) -> bool:
        return self.result == DRAW

    # -- utilities ----------------------------------------------------------

    def clone(self) -> GameState:
        gs = GameState.__new__(GameState)
        gs.board = self.board.copy()
        gs.to_move = self.to_move
        gs.result = self.result
        gs.halfmove_clock = self.halfmove_clock
        gs.hash = self.hash
        gs.counts = self.counts[:]
        gs._history = self._history[:]
        gs._rep = dict(self._rep)
        return gs

    def piece_at(self, col: int, row: int):
        from engine.pieces import decode
        return decode(self.board.sq[col * ROWS + row])
