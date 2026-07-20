# CLAUDE.md — Jungle (Dou Shou Qi)

Windows desktop **Jungle / Dou Shou Qi** game: Python 3.12 + Pygame, with a
built-in negamax AI, a polished GUI, an automated test suite, and a packaged
`.exe`. All source and assets are original to this project.

## Commands

```bat
python -m venv venv                                  &  REM optional
venv\Scripts\pip install -r requirements.txt         &  REM or use global Python
python generate_assets.py                            &  REM (re)build art + sounds
python main.py                                       &  REM run the game
python -m pytest tests\ -q                           &  REM run tests
python -m pytest tests\ --cov --cov-report=term-missing  &  REM tests + coverage
python -m ruff check .                               &  REM lint
build.bat                                            &  REM test + package exe + zip
python -m tools.strength_harness --a enhanced --b baseline --games 40 --nodes 6000  & REM A/B self-play
python -m tools.ablation --games 200 --nodes 40000   &  REM parallel feature ablation
```

The dev machine already has pygame/pytest/pyinstaller/ruff globally, so a venv
is optional. `build.bat` uses a venv if present, else the Python on PATH.

## Architecture

- `config.py` — geometry, terrain, colors, AI params, flat lookup tables
  (`sq = col*ROWS + row`), and the pure screen-sizing helpers
  (`compute_cell_size`, `layout_for_cell`).
- `engine/` — pure game logic (no pygame):
  - `pieces.py` (Color/Animal + int piece codes), `board.py` (flat board,
    Zobrist, allocation-free `apply`/`revert`), `rules.py` (capture legality),
    `move_generator.py` (moves + river jumps), `game_state.py` (turn, make/undo,
    win/draw).
- `ai/` — `evaluator.py` (antisymmetric eval), `transposition.py`, `see.py`
  (static exchange evaluation), `minimax.py` (negamax α-β + iterative deepening +
  quiescence + `SearchConfig` feature flags; `AIPlayer`). The shipped engine is
  `SearchConfig.tuned()`: PVS, null-move pruning, late-move reductions, history
  heuristic, aspiration windows, and a den-threat extension. SEE and a
  piece-square-table term exist behind flags but are **off** — self-play (200+
  games) showed each is a net negative for this engine.
- `tools/` — `strength_harness.py` (reproducible node-limited self-play between
  two `SearchConfig`s) and `ablation.py` (parallel feature ablation vs baseline).
  All strength claims are measured here, never assumed — in pure Python a change
  that searches deeper can still play weaker.
- `gui/` — `renderer.py` (all drawing + view-only flip), `input_handler.py`
  (pixel↔square, two-click), `audio.py`, `fonts.py`.
- `controller.py` — state machine (menu/playing/over), event loop, background
  AI thread (results delivered via a custom pygame event, guarded by a token).
- `main.py` — entry point: Windows DPI awareness + `SCALED|RESIZABLE` window.
- `generate_assets.py` — draws all sprites/tiles/icon and synthesises sounds.
- `tests/` — pytest suite (engine, AI, SEE, search enhancements, layout, input,
  integration).

## Key rules (keep consistent)

Coordinates `(col, row)`; 7×9; row 0 = Black (top), row 8 = Blue (bottom).
Blue moves first. **River jump:** Lion does the 4-row (over 3 river rows) and
3-col (over 2 river cols) leaps; **Tiger only the 3-col leap**; a Rat in the
water path blocks it. Rat↔Elephant special; water/land capture boundary;
enemy-trap zeroes rank; own-den entry illegal; enemy-den entry wins.

## Rendering / DPI

The UI is drawn to a fixed *logical* surface and shown via `pygame.SCALED |
RESIZABLE`, so it scales uniformly (letterboxed) to any window/monitor and is
DPI-aware (declared in `main._set_dpi_awareness`). Mouse events arrive in
logical coordinates — renderer/input are resolution-agnostic. Board flip is a
display transform only.

## Testing

`tests/` covers rules, move generation (incl. all jump variants + rat-block),
win/draw detection, board make/unmake + Zobrist, evaluator symmetry, AI tactics
/ responsiveness, the sizing helpers, input mapping, and full-game integration.
Coverage config (in `pyproject.toml`) measures the core; display/audio modules
are validated by rendering smoke tests and by running the packaged exe.
