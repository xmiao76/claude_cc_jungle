"""Integration: full games terminate with a valid result and undo stays exact."""

from ai.minimax import DIFFICULTY_EASY, AIPlayer
from engine.game_state import DRAW, GameState
from engine.move_generator import generate_moves
from engine.pieces import Color

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)


def _legal(gs, mv):
    return any(m.frm == mv.frm and m.to == mv.to for m in generate_moves(gs.board, gs.to_move))


def test_ai_vs_ai_game_completes_with_valid_result():
    gs = GameState()
    ais = {BLUE: AIPlayer(BLUE, DIFFICULTY_EASY), BLACK: AIPlayer(BLACK, DIFFICULTY_EASY)}
    plies = 0
    while not gs.game_over and plies < 400:
        mv = ais[gs.to_move].choose_move(gs)
        assert mv is not None, "AI returned no move in a non-terminal position"
        assert _legal(gs, mv), "AI produced an illegal move"
        gs.make_move(mv)
        plies += 1
    assert gs.game_over, "game did not terminate within the ply cap"
    assert gs.result in (Color.BLUE, Color.BLACK, DRAW)


def test_human_style_alternation_runs_cleanly():
    """Human picks a deterministic legal move; AI replies. No crashes / illegals."""
    gs = GameState()
    ai = AIPlayer(BLACK, DIFFICULTY_EASY)
    human = BLUE
    for _ in range(24):
        if gs.game_over:
            break
        if gs.to_move == human:
            moves = generate_moves(gs.board, human)
            gs.make_move(moves[len(moves) // 2])
        else:
            mv = ai.choose_move(gs)
            assert _legal(gs, mv)
            gs.make_move(mv)
    # Whatever happened, state is coherent.
    assert gs.counts[BLUE] >= 0 and gs.counts[BLACK] >= 0


def test_deep_undo_returns_to_initial_state():
    gs = GameState()
    ais = {BLUE: AIPlayer(BLUE, DIFFICULTY_EASY), BLACK: AIPlayer(BLACK, DIFFICULTY_EASY)}
    before_sq = gs.board.sq[:]
    before_hash = gs.hash

    played = 0
    for _ in range(12):
        if gs.game_over:
            break
        gs.make_move(ais[gs.to_move].choose_move(gs))
        played += 1
    for _ in range(played):
        gs.undo_move()

    assert gs.board.sq == before_sq
    assert gs.hash == before_hash
    assert gs.to_move == BLUE
    assert gs.counts == [8, 8]
