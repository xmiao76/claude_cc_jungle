# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Windows desktop implementation of the Jungle (Dou Shou Qi) board game, built with Python and Pygame. Supports human-vs-AI and AI-vs-AI modes with three difficulty levels.

## Common Commands

| Task | Command |
|------|---------|
| Run game (dev) | `python main.py` |
| Run all tests | `pytest tests/ -v --tb=short -q` |
| Run single test file | `pytest tests/test_rules.py -v` |
| Run with coverage | `pytest tests/ -v --cov=. --cov-report=term-missing` |
| Build release `.exe` | `build.bat` (runs tests, then PyInstaller) |
| Lint | `ruff check .` |
| Format | `ruff format .` |

The build script activates `venv\Scripts\activate.bat`, runs tests, cleans `build/` and `dist/`, runs PyInstaller with `--onefile --windowed`, and copies the result to `release\jungle_game.exe`.

## Architecture

### Layering

The codebase is split into four layers:

- **`main.py`** — Entry point. Initializes pygame, queries screen height to compute a dynamic `CELL_SIZE` (clamped 60–90px), registers a custom pygame event type for AI move results, then creates `Controller`.
- **`controller.py`** — State machine and main loop. Holds `AppState` (MENU, HUMAN_TURN, AI_THINKING, AI_VS_AI_THINKING, GAME_OVER). Wires `GameState`, `AIPlayer`, `Renderer`, `InputHandler`, and `Audio`. Handles the AI-as-thread pattern and defers AI start until human piece animations finish.
- **`engine/`** — Pure game logic with no pygame dependency.
  - `pieces.py` — `Animal` (1=Rat..8=Elephant) and `Color` (BLUE=0 south, BLACK=1 north) enums. Piece ID encoding: **positive = Blue, negative = Black, magnitude = rank**, 0 = empty.
  - `board.py` — `Board` stores `_grid[col][row]` (column-major) and maintains incremental Zobrist hashing via `make_move` / `unmake_move`.
  - `game_state.py` — `GameState` wraps `Board` with turn tracking, move history, and win detection. Exposes `copy()` for AI search.
  - `move_generator.py` — Generates all legal moves including precomputed river-jump tables for Lion and Tiger.
  - `rules.py` — `can_capture`, `effective_rank` (traps reduce rank to 0), `is_jump_blocked`, and `check_win`.
- **`gui/`** — Pygame rendering and input.
  - `renderer.py` — Draws board, piece sprites (with text fallback), menu, side panel, move history, animations, and capture flashes.
  - `input_handler.py` — Two-click model: click own piece to select and show legal targets, click target to move.
  - `audio.py` — Lazy-loading pygame.mixer wrapper; degrades silently if mixer unavailable (headless tests).
- **`ai/`** — Negamax alpha-beta search (principal variation search).
  - `minimax.py` — `AIPlayer` with fixed-depth (Easy/Medium) or iterative deepening (Hard). History is keyed by **side** (Blue and Black used to share entries), capped below the killer band, and carries a malus for quiet moves that failed to cut off. LMR never reduces a PV node or a **den-entry** move. Cancellable via `request_stop()`. PVS with aspiration windows; null-move pruning; reverse-futility / razoring / futility / late-move pruning at shallow depth; late-move reductions; mate-distance scoring; quiescence with SEE + delta pruning and **den-aware** noisy moves; killer / counter-move / history heuristics; a transposition table; MVV-LVA + SEE move ordering; timeout-robust iterative deepening that keeps the best move from an interrupted iteration and uses a soft time limit.
  - `evaluator.py` — **Purely static** position evaluation: material + advancement + den proximity + rat-in-water + trap control + mobility + tempo + jump-readiness + piece-square tables + den-threat/safety. Returns no mate or draw scores — the search owns terminality (see the mate-scale note below). Both sides run through one shared loop with a sign flip, which is what keeps it antisymmetric. Takes an optional `cfg` to gate individual terms.
  - `eval_tables.py` — Import-time tables for evaluation: orthogonal adjacency, and BFS **true moves-to-den** per movement class (walker / swimmer / lion / tiger). The BFS table exists because Manhattan distance walks straight through the river; it is currently off by default (measured weaker — see `search_config.py`).
  - `transposition.py` — Zobrist-keyed table with EXACT/LOWER/UPPER flags, **generation-based aging** (the table lives for a whole game, so without it a deep entry from an unreachable position holds its slot forever) and linear-pass eviction (the old policy sorted a million entries mid-move). Entries are tuples; `TTEntry` is a thin view.
  - `see.py` — Static Exchange Evaluation for capture sequences (used by quiescence and move ordering).
  - `opening_book.py` — Tiny hand-crafted opening book (Hard only, first dozen plies).
  - `search_config.py` — `SearchConfig` (immutable feature/tuning toggles) and the shared piece-value table. `strong_config()` is the shipped engine — **the strongest configuration actually measured, which is not "every flag on"**; `baseline_config()` disables everything and reproduces the original engine; `experimental_config()` turns on the four evaluation terms that were built, measured, and found to *lose* strength (their Elo numbers are recorded in the class docstring).

### Key Design Decisions

- **Piece ID encoding**: `make_piece_id(color, animal)` returns `+rank` for Blue and `-rank` for Black. Helpers `piece_id_color`, `piece_id_animal`, `piece_id_rank` decode it. This is the canonical representation across `Board`, `Move`, and the AI.
- **Move representation**: `Move` is a `NamedTuple` of `(fc, fr, tc, tr, captured)`. `captured` stores the piece ID of the taken piece (0 if none).
- **AI threading**: The AI search runs in a daemon thread so the UI stays responsive, and posts a custom pygame event (`config.AI_MOVE_EVENT_TYPE`) back to the main thread. Three things make that safe, and all three matter: the event carries a **generation token** that `_on_ai_move` checks (a result for a position we have left is discarded — applying one silently corrupts the grid, the Zobrist hash and the piece index); the thread body is wrapped in `try/except` (a crashed search used to post nothing and leave the game stuck in `AI_THINKING` forever, invisibly under `--windowed`); and `AIPlayer.request_stop()` lets the controller abort a search on Escape / new game / undo. `_on_ai_move` also validates the move against the current legal moves before applying it.
- **Engine feature config**: Every search/eval enhancement is gated by a flag on `ai/search_config.py:SearchConfig`, threaded through `AIPlayer(color, difficulty, cfg)` and into `evaluate(state, color, cfg)`. Per-instance, not global, so the harness can run two configs in one process.
- **Measure, do not assume.** This is the most important convention in the repo. Plausible-sounding improvements lost strength here more often than they gained it: a Rat-premium value table (-44 Elo), BFS true-distance-to-den (-70), a *corrected* jump-readiness test (-98), and static hanging-piece detection (-255, decisive) were all implemented and all measured worse than their absence. Root-move ordering by the previous iteration's scores came out at exactly 0. What did work: LMR guards (+80), TT aging (+80), side-keyed history with malus (+53). Everything that ships off is listed in `DISABLED_BY_MEASUREMENT` with its numbers in the `SearchConfig` docstring, and `test_strong_enables_every_proven_flag` fails if a flag is added without a recorded measurement. Gate any new idea behind a flag and run:
  `python -m tools.strength_harness selfplay --a strong --b <control> --games 200 --budget 250 --jobs 8`
  Read the verdict line, not the percentage: at 40 games one standard error is about 8 points, so a 55% result is not a result.
- **Mate scale (one scale only)**: `evaluate` never returns a terminal score. Mate scores come from the search as `±(_MATE - ply)`, and `_MATE < _INF` where `_INF` is only the alpha/beta sentinel. `evaluate` used to return `±_INF` for a decided position, which is *larger* than any real mate — it outranked every mate, broke mate-distance preference, and wrote out-of-window scores into the TT. Quiescence therefore owns its own no-legal-moves and 50-move checks.
- **Piece values live in one place**: `ai/search_config.py:piece_values(cfg)`. Evaluation, SEE and quiescence delta pruning must all read the same table or they disagree about what a capture is worth. SEE also orders recapturers by *value*, not rank — with a non-linear table, rank order is no longer value order.
- **Eval symmetry invariant (do not break)**: `evaluate(BLUE) == -evaluate(BLACK)` for any position (enforced by tests in `tests/test_evaluator.py`). Every per-piece positional term must be computed from the *piece's own color* (added for own pieces, subtracted for opponent pieces) — never from the evaluating side's perspective. The PST is also column-symmetric so the symmetric start position evaluates to 0 (modulo the side-to-move `tempo` bonus). Jungle has no "check"; the tactical analog is **den entry**, which is why quiescence treats den-entry moves as noisy and the eval has a den-threat term.
- **Animation deferral**: After a human move, `_pending_ai_after_anim` is set to `True`. The AI thread is not started until `renderer.has_active_animation(tick_ms)` returns `False`, so the player sees their piece finish sliding before the AI responds.
- **Board flip is visual-only**: `flipped` lives in `Controller` and `Renderer` and affects only how squares are mapped to pixels and how mouse coordinates map back to board squares (`pixel_to_board`). The engine (`Board`, `GameState`, `AI`) always sees an unflipped board. Blue always starts at row 8, Black at row 0.
- **Asset paths**: `config.asset_path(relative)` resolves paths correctly in both development and when running as a PyInstaller `--onefile` bundle (uses `sys._MEIPASS`).
- **Rat/water boundary rule**: A piece in water is invulnerable to attacks from land pieces, and vice versa, *except* Rat vs Rat on the same terrain type. Rat on land can capture Elephant on land. See `rules.py:can_capture`.
- **Trap rule — defence only**: `can_capture` applies the trap's rank-0 effect to the **defender** and never to the attacker. A piece standing in the enemy's traps can be taken by any adjacent enemy piece (Elephant included, which overrides the Elephant-cannot-take-Rat exception), but it still attacks at its full rank: vulnerable, not disarmed. The order of the checks in `can_capture` matters — water boundary, then defender-trapped, then the rank comparison with the Rat exceptions. This was the `knowIssue.txt` defect: the Elephant-vs-Rat rejection sat *before* the trap check and so never saw it. The GUI marks a trapped piece with a red rank-0 badge, because nothing on the board used to indicate it.
- **River jumps**: the river is columns {1,2} and {4,5} across rows {3,4,5}, so a **horizontal** (column-axis) leap crosses **2** river squares and a **vertical** (row-axis) leap crosses **3**. Lion makes both; **Tiger makes the horizontal 2-square leap only** (`_can_jump` allows Tiger when `dc != 0`). A rat of *either* colour on any water square along the path blocks it. Jumps are precomputed in `_build_jump_table()` at import time, and the geometry is asserted in `rust/crates/jungle-core/src/bitboard.rs`.

### Testing

Tests live in `tests/` and use pytest; configuration is in `pyproject.toml`. The engine layer needs no display. Build arbitrary positions with `tests.helpers.make_gs` — **never by writing `Board._grid` directly**, which leaves `Board.hash` at 0 and aliases every hand-built position to the same TT key, and lets two pieces of the same animal coexist so the grid and the piece index disagree. `Board.place` is the supported way in.

Two safety nets are worth knowing before changing the engine:

- **`tests/test_perft.py`** — frozen leaf counts for the start position and six tactical positions. Any change to move generation, `make_move`/`unmake_move` or the rules must leave these identical; a change means a rules change, and it has to be deliberate. Localise a mismatch with `tools.perft.perft_divide`, or `python -m tools.strength_harness perft --depth 4 --divide`.
- **`tests.helpers.assert_board_consistent`** — asserts the grid, the piece-position index and the incremental Zobrist hash all agree. This is the invariant to lean on when touching the board representation.

## File Reference

| File | Responsibility |
|------|----------------|
| `main.py` | pygame init, window sizing, custom event registration |
| `controller.py` | game loop, state machine, AI thread orchestration |
| `config.py` | constants, colors, AI depth settings, asset path helper |
| `engine/pieces.py` | enums, piece ID encoding, starting positions |
| `engine/board.py` | grid state, incremental Zobrist hashing, make/unmake |
| `engine/game_state.py` | turn, history, legal-move cache, win detection |
| `engine/move_generator.py` | all legal moves, noisy (capture + den-entry) moves, river-jump precomputation |
| `engine/rules.py` | capture rules, effective rank, jump blocking, win check |
| `ai/minimax.py` | negamax PVS, pruning (NMP/RFP/razor/futility/LMP/LMR), iterative deepening, MVV-LVA+SEE ordering, quiescence |
| `ai/evaluator.py` | static position evaluation (material, positional, PST, den-threat) |
| `ai/transposition.py` | Zobrist-keyed TT |
| `ai/see.py` | static exchange evaluation |
| `ai/opening_book.py` | hand-crafted opening book (Hard) |
| `ai/search_config.py` | `SearchConfig` feature toggles, shared piece-value table; `strong_config()` / `baseline_config()` / `experimental_config()` |
| `ai/eval_tables.py` | import-time adjacency and BFS moves-to-den tables |
| `gui/renderer.py` | all drawing: board, pieces, UI, animations |
| `gui/input_handler.py` | mouse → board action translation |
| `gui/audio.py` | sound effects with mute toggle |
| `generate_assets.py` | procedural art generation for pieces/tiles |
| `tools/strength_harness.py` | dev-only: self-play A/B match with Elo/CI/LOS, node/depth bench, perft (not bundled) |
| `tools/perft.py` | dev-only: exhaustive leaf counts — the move-generation contract |
| `tools/positions.py` | dev-only: hash-correct position builders shared by tests and harness |
| `tests/helpers.py` | shared fixtures plus `assert_board_consistent` (grid / index / hash agree) |
| `build.bat` | Windows build script (test → PyInstaller → release) |
