"""Integration tests: full AI-vs-AI game simulation."""

from ai.minimax import AIPlayer
from engine.game_state import GameState
from engine.pieces import Color
from tests.helpers import assert_board_consistent


def play_ai_game(difficulty: int = 0, max_plies: int = 300,
                 budget_ms: int = 300) -> GameState:
    """Run an AI-vs-AI game and return the final GameState.

    Returns the state rather than just the winner so callers can assert on how
    the game actually ended instead of merely that it did not crash.
    """
    gs = GameState()
    gs.new_game()

    ai_blue = AIPlayer(Color.BLUE, difficulty)
    ai_black = AIPlayer(Color.BLACK, difficulty)

    for _ in range(max_plies):
        if gs.is_terminal():
            break
        ai = ai_blue if gs.turn == Color.BLUE else ai_black
        move = ai.get_best_move(gs, time_budget_ms=budget_ms)
        if move is None:
            break
        gs.apply_move(move)

    return gs


def run_game(difficulty: int = 0, max_moves: int = 300) -> Color | None:
    """Run a full AI-vs-AI game. Return the winner, or None for a draw/cap."""
    return play_ai_game(difficulty, max_moves).get_winner()


def _assert_plausible_outcome(gs: GameState, min_plies: int) -> None:
    """Assert the game really progressed and ended in a self-consistent state."""
    assert len(gs.history) >= min_plies, (
        f"game stalled after {len(gs.history)} plies"
    )
    assert_board_consistent(gs.board)

    winner = gs.get_winner()
    if gs.result is not None:
        # A decided game: the winner must still have pieces on the board.
        assert winner is not None
        assert gs.board.alive_count(winner) > 0
    if winner is None:
        # Undecided: either the ply cap or a genuine draw, never a silent bug.
        assert not gs.result
        assert gs.board.alive_count(Color.BLUE) > 0
        assert gs.board.alive_count(Color.BLACK) > 0


# ---------------------------------------------------------------------------
# Test: AI-vs-AI game completes without crash (Easy difficulty)
# ---------------------------------------------------------------------------

def test_ai_vs_ai_completes_easy():
    """A full Easy AI-vs-AI game ends in a self-consistent state."""
    gs = play_ai_game(difficulty=0, max_plies=300)
    _assert_plausible_outcome(gs, min_plies=10)


def test_ai_vs_ai_medium_no_crash():
    """Medium AI-vs-AI holds the board invariants at every ply."""
    gs = GameState()
    gs.new_game()
    ai_blue = AIPlayer(Color.BLUE, 1)
    ai_black = AIPlayer(Color.BLACK, 1)

    plies = 0
    for _ in range(50):
        if gs.is_terminal():
            break
        ai = ai_blue if gs.turn == Color.BLUE else ai_black
        move = ai.get_best_move(gs, time_budget_ms=500)
        if move is None:
            break
        gs.apply_move(move)
        plies += 1
        # The grid, the position index and the incremental hash must all agree.
        assert_board_consistent(gs.board)

    assert plies >= 10, f"Medium game stalled after {plies} plies"


def test_game_state_consistent_throughout():
    """Throughout a game, board state invariants hold at every step."""
    gs = GameState()
    gs.new_game()
    ai_blue = AIPlayer(Color.BLUE, 0)
    ai_black = AIPlayer(Color.BLACK, 0)

    for move_num in range(100):
        if gs.is_terminal():
            break

        # Invariant: legal moves list is not empty for non-terminal state
        legal = gs.legal_moves()
        assert len(legal) > 0, f"Non-terminal position has no legal moves at move {move_num}"

        # Invariant: all legal moves reference existing pieces
        for m in legal:
            pid = gs.board.get(m.fc, m.fr)
            assert pid != 0, f"Legal move from empty square {m}"
            from engine.pieces import piece_id_color
            assert piece_id_color(pid) == gs.turn, f"Legal move for wrong color at {m}"

        ai = ai_blue if gs.turn == Color.BLUE else ai_black
        move = ai.get_best_move(gs, time_budget_ms=200)
        assert move is not None
        assert move in legal, f"AI returned a move outside the legal list: {move}"
        gs.apply_move(move)
        assert_board_consistent(gs.board)

    assert len(gs.history) >= 10, f"game stalled after {len(gs.history)} plies"


def test_undo_all_moves_restores_start():
    """Undo every move of a game to restore the starting position."""
    gs = GameState()
    gs.new_game()
    start_hash = gs.board.hash

    ai_blue = AIPlayer(Color.BLUE, 0)
    ai_black = AIPlayer(Color.BLACK, 0)

    for _ in range(20):
        if gs.is_terminal():
            break
        ai = ai_blue if gs.turn == Color.BLUE else ai_black
        move = ai.get_best_move(gs, time_budget_ms=200)
        if move:
            gs.apply_move(move)

    # Undo all moves
    while gs.history:
        gs.undo_move()

    assert gs.board.hash == start_hash, "Full undo should restore starting hash"
    assert gs.turn == Color.BLUE
    assert len(gs.history) == 0
