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
  - `board.py` — `Board` stores a FLAT 63-entry grid (`_sq[col * ROWS + row]`, v1.5) and per-color `{pid: sq}` position dicts, maintaining incremental Zobrist hashing via `make_move` / `unmake_move`. Public accessors still speak (col, row); hot engine paths index `_sq` and the flat tables in `config.py` (NEIGHBORS, TERRAIN_FLAT, TRAP_ZEROES, per-color ADV/PST/den-distance). Use `place_piece(col, row, pid)` to build test positions.
  - `game_state.py` — `GameState` wraps `Board` with turn tracking, move history, and win detection. Exposes `copy()` for AI search.
  - `move_generator.py` — Generates all legal moves including precomputed river-jump tables for Lion and Tiger. Also a dedicated `generate_noisy_only` (captures + den entries, no quiet-move pass) for quiescence.
  - `rules.py` — `can_capture`, `effective_rank` (traps reduce rank to 0), `is_jump_blocked`, and `check_win`.
- **`gui/`** — Pygame rendering and input.
  - `renderer.py` — Draws board, piece sprites (with text fallback), menu, side panel, move history, animations, and capture flashes.
  - `input_handler.py` — Two-click model: click own piece to select and show legal targets, click target to move.
  - `audio.py` — Lazy-loading pygame.mixer wrapper; degrades silently if mixer unavailable (headless tests).
- **`ai/`** — Negamax alpha-beta search (principal variation search).
  - `minimax.py` — `AIPlayer` with fixed-depth (Easy/Medium) or iterative deepening (Hard). PVS with aspiration windows; null-move pruning; reverse-futility / razoring / futility / late-move pruning at shallow depth; late-move reductions; mate-distance scoring; quiescence with SEE + delta pruning and **den-aware** noisy moves; killer / counter-move / history heuristics; a transposition table; MVV-LVA + SEE move ordering; timeout-robust iterative deepening that keeps the best move from an interrupted iteration and uses a soft time limit. v1.4 additions: path-cycle/third-visit repetition scoring (`use_search_repetition`), hot-path noisy movegen + non-terminal eval (`use_fast_movegen`), TT static-eval reuse and quiescence TT move (`use_tt_static_eval`, `use_qsearch_tt_move`), and a stability-based per-player time bank (`use_stability_time`). v1.5 additions: log-based LMR matrix with history/PV adjustments (`use_lmr_matrix`), improving heuristic modulating RFP/futility/LMP (`use_improving`), continuation history (`use_cont_history`).
  - `evaluator.py` — Position evaluation: material + advancement + den proximity + rat-in-water + trap control + mobility + tempo + jump-readiness + **piece-square tables** + **den-threat/safety** + **hanging-piece penalty** (`use_hanging_penalty`, v1.5). Per-piece terms use the piece's own-color advancement so eval stays antisymmetric (`evaluate(BLUE) == -evaluate(BLACK)`). Takes an optional `cfg` to gate the PST/den-threat/hanging terms and to select the weight table (`use_tuned_weights` → `EVAL_WEIGHTS_TUNED`; currently identical to the hand weights — see tools/tune_eval.py's v1.5 finding). `evaluate_nonterminal` skips terminal detection for hot search paths; `_evaluate_core` holds the terms; `evaluate_features` exposes raw feature counts for the tuner (dot-product identity pinned by test).
  - `transposition.py` — Zobrist-keyed transposition table with EXACT/LOWER/UPPER flags. Two replacement policies: legacy depth-prefer with halving-sort eviction (v1.3, kept for the frozen configs) and generation aging with O(1) eviction (v1.4). Entries carry an optional cached static eval.
  - `see.py` — Static Exchange Evaluation for capture sequences (used by quiescence and move ordering).
  - `opening_book.py` — Tiny hand-crafted opening book (Hard only, first dozen plies).
  - `search_config.py` — `SearchConfig` (immutable feature/tuning toggles). `strong_config()` enables every enhancement (the shipped default); `baseline_config()` disables them all and reproduces the original engine; `v13_strong_config()` / `v14_strong_config()` freeze the exact flag-sets of the shipped v1.3/v1.4 engines so each release is measured against the previous one.

### Key Design Decisions

- **Piece ID encoding**: `make_piece_id(color, animal)` returns `+rank` for Blue and `-rank` for Black. Helpers `piece_id_color`, `piece_id_animal`, `piece_id_rank` decode it. This is the canonical representation across `Board`, `Move`, and the AI.
- **Move representation**: `Move` is a `NamedTuple` of `(fc, fr, tc, tr, captured)`. `captured` stores the piece ID of the taken piece (0 if none).
- **AI threading**: The AI search runs in a daemon thread (`threading.Thread`) so the UI remains responsive. When the search finishes, it posts a custom pygame event (`config.AI_MOVE_EVENT_TYPE`) back to the main thread. The controller processes this in `_handle_events` via `_on_ai_move`.
- **Engine feature config**: Every search/eval enhancement is gated by a flag on `ai/search_config.py:SearchConfig`, threaded through `AIPlayer(color, difficulty, cfg)` and into `evaluate(state, color, cfg)`. The default (`cfg=None` / `strong_config()`) enables everything. `baseline_config()` disables everything to reproduce the original engine; `v13_strong_config()` / `v14_strong_config()` reproduce the shipped v1.3/v1.4 engines (registered as `v13`/`v14` in the harness). This is per-instance (not a global), so the strength harness can run two configs in one process. To measure any change, run `python -m tools.strength_harness selfplay --a strong --b v14` (self-play match against the previous release) or `... bench` (node/depth benchmark). Fixed-depth signature tests in `tests/test_strength.py` pin the flag-off code paths byte-for-byte: if one fails, a change leaked outside its flag (game-RULES fixes are the one sanctioned reason to re-pin, in a dedicated documented commit). Note that self-play matches at short budgets are timing-noisy — an identical-config A/A match scored 62.5% over 40 games — so strength claims need 200+ games on multiple seeds with an otherwise idle machine.
- **Eval symmetry invariant (do not break)**: `evaluate(BLUE) == -evaluate(BLACK)` for any position (enforced by tests in `tests/test_evaluator.py`). Every per-piece positional term must be computed from the *piece's own color* (added for own pieces, subtracted for opponent pieces) — never from the evaluating side's perspective. The PST is also column-symmetric so the symmetric start position evaluates to 0 (modulo the side-to-move `tempo` bonus). Jungle has no "check"; the tactical analog is **den entry**, which is why quiescence treats den-entry moves as noisy and the eval has a den-threat term.
- **Animation deferral**: After a human move, `_pending_ai_after_anim` is set to `True`. The AI thread is not started until `renderer.has_active_animation(tick_ms)` returns `False`, so the player sees their piece finish sliding before the AI responds.
- **Board flip is visual-only**: `flipped` lives in `Controller` and `Renderer` and affects only how squares are mapped to pixels and how mouse coordinates map back to board squares (`pixel_to_board`). The engine (`Board`, `GameState`, `AI`) always sees an unflipped board. Blue always starts at row 8, Black at row 0.
- **Asset paths**: `config.asset_path(relative)` resolves paths correctly in both development and when running as a PyInstaller `--onefile` bundle (uses `sys._MEIPASS`).
- **Rat/water boundary rule**: A piece in water is invulnerable to attacks from land pieces, and vice versa, *except* Rat vs Rat on the same terrain type. Rat on land can capture Elephant on land. See `rules.py:can_capture`.
- **River jumps**: Lion can jump horizontally across 3 river squares and vertically across 2. Tiger can jump horizontally across 2 river squares only. A rat on any water square along the jump path blocks it. Jumps are precomputed in `_build_jump_table()` at import time.

### Testing

Tests live in `tests/` and use pytest. The engine layer is fully testable without a display (pygame display is not initialized in pure engine tests). `test_full_game.py` replays recorded move sequences to verify end-to-end rule compliance. `test_ai.py` tests search correctness and timeout behavior.

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
| `ai/search_config.py` | `SearchConfig` feature toggles; `strong_config()` / `baseline_config()` / `v13_strong_config()` |
| `gui/renderer.py` | all drawing: board, pieces, UI, animations |
| `gui/input_handler.py` | mouse → board action translation |
| `gui/audio.py` | sound effects with mute toggle |
| `generate_assets.py` | procedural art generation for pieces/tiles |
| `tools/strength_harness.py` | dev-only: self-play A/B match + node/depth bench (not bundled) |
| `tools/tune_eval.py` | dev-only: Texel tuning — self-play position harvest + logistic weight fit |
| `build.bat` | Windows build script (test → PyInstaller → release) |
